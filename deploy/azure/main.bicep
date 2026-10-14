// FeedbackFlow on Azure: Container Registry + Container Apps (API, notifier) + Database for PostgreSQL.
// Deployed by deploy/azure/bootstrap.sh; GitHub Actions then only pushes images and updates revisions.

targetScope = 'resourceGroup'

@description('Region for every resource.')
param location string = resourceGroup().location

@description('Region for PostgreSQL. Student subscriptions restrict flexible servers in some regions.')
param postgresLocation string = location

@description('Short prefix for resource names.')
@maxLength(12)
param prefix string = 'feedbackflow'

@description('Create the container apps. False on the first pass, before any image exists in the registry.')
param deployApps bool = true

@description('Full image references, e.g. myacr.azurecr.io/feedbackflow-app:<sha>.')
param appImage string = ''
param notifierImage string = ''

@description('GitHub repository (owner/name) allowed to deploy from its main branch via OIDC.')
param githubRepo string

param postgresAdminUser string = 'feedbackflow'

@secure()
param postgresAdminPassword string

@secure()
param demoPassword string

@secure()
param notifierToken string

@secure()
@description('Comma-separated webhook URLs (e.g. a Slack incoming webhook). Empty = events are accepted but not sent.')
param webhookUrls string = ''

@secure()
param webhookSecret string = ''

@allowed(['json', 'slack'])
param webhookFormat string = 'json'

var suffix = uniqueString(resourceGroup().id)
var appName = '${prefix}-app'
var notifierName = '${prefix}-notifier'
var databaseName = 'feedbackflow'

var roles = {
  acrPull: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  acrPush: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8311e382-0749-4cb8-b61a-304f252e45ec')
  contributor: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')
}

// --- Registry & identities -----------------------------------------------------------------

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: '${replace(prefix, '-', '')}${suffix}'
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

@description('Used by the container apps to pull images (no registry passwords anywhere).')
resource pullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-pull'
  location: location
}

resource pullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, pullIdentity.id, 'AcrPull')
  scope: registry
  properties: {
    roleDefinitionId: roles.acrPull
    principalId: pullIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

@description('Assumed by GitHub Actions through OIDC federation: no long-lived Azure credentials in GitHub.')
resource githubIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-github'
  location: location
}

resource githubFederation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: githubIdentity
  name: 'github-main'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:${githubRepo}:ref:refs/heads/main'
    audiences: ['api://AzureADTokenExchange']
  }
}

resource githubPushRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, githubIdentity.id, 'AcrPush')
  scope: registry
  properties: {
    roleDefinitionId: roles.acrPush
    principalId: githubIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource githubDeployRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, githubIdentity.id, 'Contributor')
  properties: {
    roleDefinitionId: roles.contributor
    principalId: githubIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// --- PostgreSQL ------------------------------------------------------------------------------

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: '${prefix}-pg-${suffix}'
  location: postgresLocation
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '16'
    administratorLogin: postgresAdminUser
    administratorLoginPassword: postgresAdminPassword
    storage: { storageSizeGB: 32, autoGrow: 'Disabled' }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
    network: { publicNetworkAccess: 'Enabled' }
    authConfig: { passwordAuth: 'Enabled', activeDirectoryAuth: 'Disabled' }
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgres
  name: databaseName
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}

// 0.0.0.0 is Azure's convention for "allow connections from Azure services": Container Apps on the
// Consumption plan have no fixed egress IP. TLS and the password still protect the server.
resource allowAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: postgres
  name: 'AllowAzureServices'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
}

// --- Container Apps --------------------------------------------------------------------------

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${prefix}-logs'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: 1 }
  }
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${prefix}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

var registryAuth = [{ server: registry.properties.loginServer, identity: pullIdentity.id }]
var appUrl = 'https://${appName}.${environment.properties.defaultDomain}'
var databaseUrl = 'postgresql+psycopg://${postgresAdminUser}:${uriComponent(postgresAdminPassword)}@${postgres.properties.fullyQualifiedDomainName}:5432/${databaseName}?sslmode=require'

resource notifier 'Microsoft.App/containerApps@2024-03-01' = if (deployApps) {
  name: notifierName
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${pullIdentity.id}': {} } }
  dependsOn: [pullRole]
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      // Internal only: reachable from apps in this environment, not from the internet.
      ingress: { external: false, targetPort: 8002, transport: 'http' }
      registries: registryAuth
      secrets: [
        { name: 'notifier-token', value: notifierToken }
        { name: 'webhook-urls', value: webhookUrls }
        { name: 'webhook-secret', value: webhookSecret }
      ]
    }
    template: {
      containers: [
        {
          name: 'notifier'
          image: notifierImage
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
          env: [
            { name: 'APP_ENV', value: 'production' }
            { name: 'WEBHOOK_FORMAT', value: webhookFormat }
            { name: 'NOTIFIER_TOKEN', secretRef: 'notifier-token' }
            { name: 'WEBHOOK_URLS', secretRef: 'webhook-urls' }
            { name: 'WEBHOOK_SECRET', secretRef: 'webhook-secret' }
          ]
          probes: [
            { type: 'Liveness', httpGet: { path: '/healthz', port: 8002 }, periodSeconds: 20 }
            { type: 'Readiness', httpGet: { path: '/readyz', port: 8002 }, periodSeconds: 10 }
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: 1 }
    }
  }
}

resource app 'Microsoft.App/containerApps@2024-03-01' = if (deployApps) {
  name: appName
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${pullIdentity.id}': {} } }
  dependsOn: [pullRole, database, allowAzure]
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      ingress: { external: true, targetPort: 8000, transport: 'auto', allowInsecure: false }
      registries: registryAuth
      secrets: [
        { name: 'database-url', value: databaseUrl }
        { name: 'demo-password', value: demoPassword }
        { name: 'notifier-token', value: notifierToken }
      ]
    }
    template: {
      containers: [
        {
          name: 'app'
          image: appImage
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'APP_ENV', value: 'production' }
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'DEMO_PASSWORD', secretRef: 'demo-password' }
            { name: 'CORS_ORIGINS', value: appUrl }
            { name: 'NOTIFIER_URL', value: deployApps ? 'https://${notifier!.properties.configuration.ingress.fqdn}' : '' }
            { name: 'NOTIFIER_TOKEN', secretRef: 'notifier-token' }
            // The notifier may be scaled to zero; publishing runs after the response, so waiting is harmless.
            { name: 'NOTIFIER_TIMEOUT_SECONDS', value: '20' }
          ]
          probes: [
            {
              type: 'Startup'
              httpGet: { path: '/api/health', port: 8000 }
              periodSeconds: 5
              failureThreshold: 24
            }
            { type: 'Readiness', httpGet: { path: '/api/health', port: 8000 }, periodSeconds: 10, timeoutSeconds: 5 }
            { type: 'Liveness', httpGet: { path: '/api/health/live', port: 8000 }, periodSeconds: 20 }
          ]
        }
      ]
      // One replica: analysis runs in-process and rate limits are per-process. Scales to zero when idle.
      scale: { minReplicas: 0, maxReplicas: 1 }
    }
  }
}

output registryName string = registry.name
output registryLoginServer string = registry.properties.loginServer
output appName string = appName
output notifierName string = notifierName
output appUrl string = appUrl
output postgresHost string = postgres.properties.fullyQualifiedDomainName
output githubClientId string = githubIdentity.properties.clientId

import { buildApp } from "./app.js";
import { loadConfig } from "./config.js";

const config = loadConfig();
const app = buildApp({ config, logger: { level: config.logLevel } });

if (!config.webhookUrls.length) app.log.warn("WEBHOOK_URLS is empty: events will be accepted but not delivered");

// Kubernetes and Container Apps send SIGTERM before killing the pod: finish in-flight deliveries first.
for (const signal of ["SIGTERM", "SIGINT"] as const) {
  process.once(signal, () => {
    app.log.info({ signal }, "shutting down");
    app.close().then(
      () => process.exit(0),
      (error) => {
        app.log.error(error, "shutdown failed");
        process.exit(1);
      },
    );
  });
}

try {
  await app.listen({ port: config.port, host: config.host });
} catch (error) {
  app.log.error(error);
  process.exit(1);
}

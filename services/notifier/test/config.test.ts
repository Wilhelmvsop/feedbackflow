import { describe, expect, it } from "vitest";
import { loadConfig } from "../src/config.js";

describe("loadConfig", () => {
  it("has development defaults", () => {
    expect(loadConfig({})).toMatchObject({
      port: 8002,
      ingestToken: null,
      webhookUrls: [],
      webhookFormat: "json",
      deliveryAttempts: 4,
    });
  });

  it("parses lists and numbers", () => {
    const config = loadConfig({
      WEBHOOK_URLS: " https://a.example/x , http://b.example/y ,",
      PORT: "9000",
      DELIVERY_ATTEMPTS: "2",
      WEBHOOK_FORMAT: "slack",
      NOTIFIER_TOKEN: "  t  ",
    });
    expect(config).toMatchObject({
      webhookUrls: ["https://a.example/x", "http://b.example/y"],
      port: 9000,
      deliveryAttempts: 2,
      webhookFormat: "slack",
      ingestToken: "t",
    });
  });

  it("rejects invalid values", () => {
    expect(() => loadConfig({ WEBHOOK_URLS: "not a url" })).toThrow();
    expect(() => loadConfig({ WEBHOOK_URLS: "ftp://example.com" })).toThrow(/Unsupported/);
    expect(() => loadConfig({ WEBHOOK_FORMAT: "xml" })).toThrow(/WEBHOOK_FORMAT/);
    expect(() => loadConfig({ DELIVERY_ATTEMPTS: "0" })).toThrow(/DELIVERY_ATTEMPTS/);
    expect(() => loadConfig({ PORT: "abc" })).toThrow(/PORT/);
  });

  it("requires an ingest token outside development", () => {
    expect(() => loadConfig({ APP_ENV: "production" })).toThrow(/NOTIFIER_TOKEN/);
    expect(loadConfig({ APP_ENV: "production", NOTIFIER_TOKEN: "x" }).ingestToken).toBe("x");
  });
});

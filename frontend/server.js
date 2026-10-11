const cluster = require("node:cluster");
const http = require("node:http");
const next = require("next");

const dev = process.env.NODE_ENV !== "production";
const hostname = process.env.HOSTNAME || "0.0.0.0";
const port = parseInt(process.env.PORT || "3000", 10);
const numWorkers = parseInt(
  process.env.WEB_CONCURRENCY || process.env.NODE_WORKERS || "4",
  10
);

if (cluster.isPrimary) {
  console.log(`[Primary ${process.pid}] Starting Next.js cluster with ${numWorkers} workers on port ${port}...`);

  for (let i = 0; i < numWorkers; i++) {
    cluster.fork();
  }

  cluster.on("online", (worker) => {
    console.log(`[Worker ${worker.process.pid}] Online and ready`);
  });

  cluster.on("exit", (worker, code, signal) => {
    console.warn(
      `[Worker ${worker.process.pid}] Died (code: ${code}, signal: ${signal}). Spawning replacement worker...`
    );
    cluster.fork();
  });
} else {
  const app = next({ dev, hostname, port });
  const handle = app.getRequestHandler();

  app
    .prepare()
    .then(() => {
      const server = http.createServer(async (req, res) => {
        try {
          await handle(req, res);
        } catch (err) {
          console.error(`[Worker ${process.pid}] Request error:`, err);
          if (!res.headersSent) {
            res.statusCode = 500;
            res.end("Internal Server Error");
          }
        }
      });

      server.listen(port, hostname, () => {
        console.log(`[Worker ${process.pid}] Listening on http://${hostname}:${port}`);
      });
    })
    .catch((err) => {
      console.error(`[Worker ${process.pid}] Failed to prepare Next.js app:`, err);
      process.exit(1);
    });
}

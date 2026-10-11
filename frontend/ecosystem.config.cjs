module.exports = {
  apps: [
    {
      name: "revops-frontend",
      script: "server.js",
      instances: 1, // server.js handles 4 workers via cluster module internally
      autorestart: true,
      watch: false,
      env_production: {
        NODE_ENV: "production",
        NODE_WORKERS: "4",
        PORT: 3000,
      },
    },
  ],
};

module.exports = {
  apps: [
    {
      name: "ipo-wise-bot",
      script: "main.py",
      interpreter: "python3",
      cwd: "/home/kurieneapenk_dev/ipo-alert-bot",
      env: {
        PORT: 5050,
        HOST: "127.0.0.1",
        BASE_PATH: "/ipo",
        ADMIN_PASSWORD: "admin123"
      },
      restart_delay: 4000,
      max_restarts: 10,
      autorestart: true
    }
  ]
};

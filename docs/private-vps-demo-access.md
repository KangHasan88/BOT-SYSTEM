# Private VPS Demo Access

VPS demo harus private. Dashboard bot tidak boleh dibuka sebagai public
unauthenticated website.

## Target

- Orchestrator web di VPS bind ke `127.0.0.1:8000`.
- User membuka dashboard dari laptop lewat SSH tunnel.
- Tidak ada port public untuk web orchestrator.
- Real live tetap disabled.
- Akses demo hanya untuk paper/research monitoring.

## VPS Service

Install service private web orchestrator:

```bash
sudo cp deploy/systemd/trading-bot-orchestrator.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now trading-bot-orchestrator.service
sudo systemctl status trading-bot-orchestrator.service
```

Service ini menjalankan:

```text
serve-orchestrator --config /etc/trading-bot/bot.toml --host 127.0.0.1 --port 8000
```

Binding ke `127.0.0.1` berarti browser publik tidak bisa langsung membuka
dashboard dari internet.

## Laptop Access

Dari laptop Windows, jalankan:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-vps-demo-tunnel.ps1 -SshUser tradingbot -SshHost 31.97.106.123 -LocalPort 18000 -RemotePort 8000
```

Lalu buka:

```text
http://127.0.0.1:18000/
```

Tunnel akan meneruskan traffic dari laptop ke `127.0.0.1:8000` di VPS. Tutup
terminal atau tekan `Ctrl+C` untuk memutus akses.

## Smoke Check

Di VPS:

```bash
curl -sS http://127.0.0.1:8000/api/setup
curl -sS http://127.0.0.1:8000/api/local-demo
curl -sS http://127.0.0.1:8000/api/paper-campaign
```

Dari laptop setelah tunnel aktif:

```powershell
Invoke-RestMethod http://127.0.0.1:18000/api/setup
Invoke-RestMethod http://127.0.0.1:18000/api/local-demo
Invoke-RestMethod http://127.0.0.1:18000/api/paper-campaign
```

## Public Exposure Rejection

Konfigurasi berikut ditolak untuk v1:

- `--host 0.0.0.0`;
- expose port `8000` langsung ke internet;
- reverse proxy publik tanpa auth;
- dashboard yang punya tombol live order;
- API key live/withdrawal untuk demo.

Jika akses publik benar-benar dibutuhkan di masa depan, harus dibuat card baru
untuk VPN/auth/security review. Default tetap SSH tunnel atau VPN private.

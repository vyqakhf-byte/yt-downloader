# Video Downloader Website

A small website: paste a video link, see its title and thumbnail, pick a
quality (Best / 1080p / 720p / 480p / 360p / Audio MP3), and download it.
Built with Flask + yt-dlp. Downloaded files are sent to your browser and
then removed from the server.

## Run it

**Sab se asaan tareeqa:** Windows par `run.bat` par double-click karo
(Mac/Linux par `run.sh` chalao). Pehli dafa setup khud ho jayega aur
browser khud khul jayega. Terminal me commands likhne ki zaroorat nahi.

Ya manually:

```bash
cd yt-downloader
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python app.py
```

Then open http://127.0.0.1:5000 in your browser.

ffmpeg alag se install ho to wahi use hoga; warna app pehli zaroorat
par ek static ffmpeg/ffprobe build khud download kar leti hai (is liye
pehli MP3 download me thora waqt lag sakta hai).

## Blogger par chalana

Blogger sirf static pages host karta hai — is liye ye Python app seedha
Blogger par nahi chal sakti. Tareeqa ye hai: backend kahin aur chalao,
design Blogger par lagao.

1. Backend Render par deploy karo (neeche tareeqa) — tumhe ek link
   milega, jaise `https://yt-downloader-xxxx.onrender.com`.
2. Blogger me ek Page ya Layout gadget kholo, HTML view me
   `blogger.html` ka poora content paste karo.
3. Upar wale "Backend link" box me apna Render link daal kar Save dabao.
4. Bas — Blogger page se video download kaam karega, kyunki page
   backend se baat karega. Backend link `https` hona chahiye.

## Render par backend deploy karna (free)

1. Ye folder GitHub par daalo (nayi repository).
2. Render.com par free account banao, "New Web Service" me wo repository
   chuno. `render.yaml` ki wajah se settings khud lag jayengi.
3. Deploy hone ke baad jo link mile, wo `blogger.html` me daalo.
4. Note: Render ka free plan khali rehne par so jata hai, pehli request
   par jagane me ~1 minute lag sakta hai.

## How it works

- `GET /` serves the page (`templates/index.html`).
- `POST /api/info` with `{"url": "..."}` returns title, uploader,
  thumbnail and duration.
- `POST /api/download` with `{"url": "...", "quality": "720"}` downloads
  the video on the server and returns it as a file download.

## Notes

- Only download videos you own or that are free to download. YouTube's
  terms do not allow downloading most videos, and creators' rights apply.
- If YouTube asks for a sign-in ("Sign in to confirm you're not a bot")
  on a server, yt-dlp may need a browser cookies file. In that case add
  `"cookiefile": "cookies.txt"` to the options in `app.py` (export the
  cookies from a browser where you are signed in).
- For a public site, add your own safeguards: rate limiting, a download
  size cap, and a queue, since one download at a time can be slow.

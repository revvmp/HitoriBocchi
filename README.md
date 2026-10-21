<p align="center">
  <img src="frontend/public/bocchi_slug.png" alt="HitoriBocchi logo" width="128">
</p>

<h1 align="center">HitoriBocchi</h1>


## About

HitoriBocchi is a self-hosted anime and manga website offering ad-less episodes and chapters.

## Tech Stack
- **Frontend:** Next.js 16
- **Backend:** Python 3.14
- **TypeScript:** 5+
- **Node.js:** 20.9+


## Development Setup

### Set Up the Backend

Open up a terminal

```powershell
cd backend
python -m venv venv
venv/Scripts/Activate
pip install -r requirements.txt
```

Create `backend/.env` and add the following configuration:

```dotenv
SECRET_KEY=replace-with-a-long-random-secret
JWT_SECRET_KEY=replace-with-another-long-random-secret
JWT_ACCESS_TOKEN_EXPIRES=15
JWT_REFRESH_TOKEN_EXPIRES=30
REGISTRATION_KEY=replace-with-a-private-registration-key
JWT_COOKIE_SECURE=false #True if running for production
```

Initialize the SQLite database:

```powershell
cd backend/src
python -m database.create_database
```


Database initialization creates an admin account with username `admin` and password `admin`.

Start the Flask development server from `backend/src`:

```powershell
flask --app main run --debug
```


### Set Up the Frontend

Open up a second terminal

```powershell
cd frontend
npm install
npm run dev
```

Your website will be at [http://localhost:3000](http://localhost:3000) on the browser.


## Synchronization Jobs

Run jobs from `backend/src` with the Python virtual environment activated

```powershell
python -m jobs.sync_seasonal_animes
python -m jobs.sync_anime_episodes
python -m jobs.sync_manga_chapters
python -m jobs.seed_manga_catalog --limit 500 --sync-chapters
python -m jobs.sync_upcoming_anime_metadata
python -m jobs.sync_anime_metadata
```

| Job | Purpose | Suggested Schedule |
| --- | --- | --- |
| `sync_seasonal_animes.py` | Adds new TV anime from the current MAL season | Monthly |
| `sync_anime_episodes.py` | Adds missing episodes for ongoing anime | Every 30-60 minutes |
| `sync_manga_chapters.py` | Adds missing chapters for publishing manga and manhwa | Every 30-60 minutes |
| `seed_manga_catalog.py` | Imports popular MAL manga and manhwa available on MangaKatana and resumes from a checkpoint | Run on demand |
| `sync_upcoming_anime_metadata.py` | Refreshes metadata only for anime stored as `Not yet aired` | Daily |
| `sync_anime_metadata.py` | Refreshes MAL-managed metadata such as ratings and status | Weekly |


## Production

1. Open up two terminals and set up your environment.
2. Start the Flask server.
```powershell
cd backend
python -m venv venv
venv/Scripts/Activate
pip install -r requirements.txt
cd src
python main.py
```
3. Open up the other terminal.
4. Start the Nextjs server.
```powershell
npm run build
npm start
```
5. You can access your website locally at `http://public_ipv4_address:3000/`.

## Gallery

<img width="2076" height="1296" alt="image" src="https://github.com/user-attachments/assets/586650a9-dd34-47ea-8c70-f2cfdf697a96" />

<img width="1957" height="1012" alt="image" src="https://github.com/user-attachments/assets/527ff8ef-fc36-4de9-9276-0c44f8267884" />

<img width="1990" height="1286" alt="image" src="https://github.com/user-attachments/assets/67dcae86-85af-479d-888d-316947ac40c8" />

## Disclaimer

This project is for educational purposes only.

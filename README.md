# Kino-Swipe 
[![Docker Pulls](https://img.shields.io/docker/pulls/bergasha/kino-swipe)](https://hub.docker.com/r/bergasha/kino-swipe)

Always trying to decide on a movie to watch together?, This may be the fun solution you've been looking for.
Dating app style swipe right for like swipe left for nope, If you both swipe right on the 
same movie, IT'S A MATCH!!



## Demo
<img width="320" height="640" alt="1" src="https://github.com/user-attachments/assets/4517d22b-aba7-419f-8fc1-19cf5b93af8d" />
<img width="320" height="640" alt="4" src="https://github.com/user-attachments/assets/3dea1bdc-3bb4-43aa-879d-ae5b6b85b6ef" />
<img width="320" height="640" alt="3" src="https://github.com/user-attachments/assets/f95ae259-8a1d-4021-a344-ea0dc288f905" />
<img width="320" height="640" alt="2" src="https://github.com/user-attachments/assets/d23fad4e-6f39-4ba8-9840-d1c8b745cd38" />
<img width="320" height="640" alt="5" src="https://github.com/user-attachments/assets/3f1199eb-c21e-405c-8b27-7323585efe5c" />


<div align="center">
  <video src="https://github.com/user-attachments/assets/37a2a485-ef1f-4c45-9eea-7a858323e01a" 
    width="750" 
    autoplay 
    loop 
    muted 
    playsinline>
  </video>
</div>




## Features
- **Plex Integration:** Connects directly to your server to pull random movies.
- **Real-Time Sync:** Host a room, share a 4-digit code, and swipe with a partner instantly.
- **Visual Feedback:** Faint Red/Green "glow" overlays that react as you drag the posters left or right.
- **Select Genre:** Both sessions will stay in sync while browsing genres.
- **Add to watchlist:** Tap on each match and either open in Plex or add to watchlist for later.
- **Watch trailer** Tap on the main poster in swipedeck for full synopsis and even watch the trailer. 
- **PWA Support:** Add it to your Home Screen for a native app feel.
- **Match Notifications:** Instant alerts when you both swipe right on the same movie.
- **Match History** All matches now live in Match History until you're ready to delete them.
- **Solo Mode** Flying solo? no worries, just host session and flick the solo toggle. (Every right swipe saves to Match History) 

## Coming Soon
~~Match History: Match history folder accessible outside session for easy access.~~   
  

## Requirements
- **Plex Media Server**
- **Plex Auth Token**
- **TMDB key for trailers** (Not required but trailers will not work on the back of the posters)
- **HTTPS/Reverse Proxy:** To "Install" the app as a PWA on your phone so it looks like an app, you must access it over an HTTPS connection. If you access it over local ip, it will work in the browser but when added to homescreen it will just act as a shortcut not like an app.

## TMDB API instructions
Only required if you want trailers to work on the rear of the movie posters.

1. Create a free TMDB Account
If you don't already have one, you need to register on the TMDB website:

Go to themoviedb.org/signup.

Verify your email address to activate the account.

2. Access the API Settings
Once logged in:

Click on your Profile Icon in the top right corner of the screen.

Select Settings from the dropdown menu.

On the left-hand sidebar, click on API.

3. Create an API Key
Under the "Request an API Key" section, click on the link for Create.

You will be asked to choose a type of API key. Select Developer.

Accept the Terms of Use.

Fill out the form: * Type of Use: Personal/Educational.

Application Name: Kino-Swipe.

Application URL: (You can put localhost or your server's IP).

Application Summary: "An app to help find movies to watch from my Plex library with a Tinder-style swipe interface."

Submit the form.

4. Copy your API Key
You will now see two different keys. For Kino-Swipe, you need the API Key (v3 auth). It is a long string of numbers and letters.
---

## Deployment

### Option 1: Docker (Recommended)
Copy and paste this into your terminal. Replace the variables with your specific setup.

```bash
services:
  kino-swipe:
    image: bergasha/kino-swipe:latest
    container_name: kino-swipe
    ports:
      - "5005:5005"
    environment:
      - PLEX_URL=https://YOUR_PLEX_IP:32400
      - PLEX_TOKEN=YOUR_PLEX_TOKEN
      - FLASK_SECRET=SomeRandomString
      - TMDB_API_KEY=your_copied_tmdb_key_here
    volumes:
      - ./data:/app/data
      - ./static:/app/static
    restart: unless-stopped
```

**Option 2 — Docker Run**
```bash
docker run -d \
  --name kino-swipe \
  -p 5005:5005 \
  -e PLEX_URL=https://YOUR_PLEX_IP:32400 \
  -e PLEX_TOKEN=YOUR_PLEX_TOKEN \
  -e FLASK_SECRET=SomeRandomString \
  -e TMDB_API_KEY=your_copied_tmdb_key_here \
  -v ./data:/app/data \
  -v ./static:/app/static \
  --restart unless-stopped \
  bergasha/kino-swipe:latest
```

![tmdb](https://github.com/user-attachments/assets/97e2c08b-5421-4f16-a798-acca2bb76a60)
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 273.42 35.52"><defs><style>.cls-1{fill:url(#linear-gradient);}</style><linearGradient id="linear-gradient" y1="17.76" x2="273.42" y2="17.76" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#90cea1"/><stop offset="0.56" stop-color="#3cbec9"/><stop offset="1" stop-color="#00b3e5"/></linearGradient></defs><title>Asset 3</title><g id="Layer_2" data-name="Layer 2"><g id="Layer_1-2" data-name="Layer 1"><path class="cls-1" d="M191.85,35.37h63.9A17.67,17.67,0,0,0,273.42,17.7h0A17.67,17.67,0,0,0,255.75,0h-63.9A17.67,17.67,0,0,0,174.18,17.7h0A17.67,17.67,0,0,0,191.85,35.37ZM10.1,35.42h7.8V6.92H28V0H0v6.9H10.1Zm28.1,0H46V8.25h.1L55.05,35.4h6L70.3,8.25h.1V35.4h7.8V0H66.45l-8.2,23.1h-.1L50,0H38.2ZM89.14.12h11.7a33.56,33.56,0,0,1,8.08,1,18.52,18.52,0,0,1,6.67,3.08,15.09,15.09,0,0,1,4.53,5.52,18.5,18.5,0,0,1,1.67,8.25,16.91,16.91,0,0,1-1.62,7.58,16.3,16.3,0,0,1-4.38,5.5,19.24,19.24,0,0,1-6.35,3.37,24.53,24.53,0,0,1-7.55,1.15H89.14Zm7.8,28.2h4a21.66,21.66,0,0,0,5-.55A10.58,10.58,0,0,0,110,26a8.73,8.73,0,0,0,2.68-3.35,11.9,11.9,0,0,0,1-5.08,9.87,9.87,0,0,0-1-4.52,9.17,9.17,0,0,0-2.63-3.18A11.61,11.61,0,0,0,106.22,8a17.06,17.06,0,0,0-4.68-.63h-4.6ZM133.09.12h13.2a32.87,32.87,0,0,1,4.63.33,12.66,12.66,0,0,1,4.17,1.3,7.94,7.94,0,0,1,3,2.72,8.34,8.34,0,0,1,1.15,4.65,7.48,7.48,0,0,1-1.67,5,9.13,9.13,0,0,1-4.43,2.82V17a10.28,10.28,0,0,1,3.18,1,8.51,8.51,0,0,1,2.45,1.85,7.79,7.79,0,0,1,1.57,2.62,9.16,9.16,0,0,1,.55,3.2,8.52,8.52,0,0,1-1.2,4.68,9.32,9.32,0,0,1-3.1,3A13.38,13.38,0,0,1,152.32,35a22.5,22.5,0,0,1-4.73.5h-14.5Zm7.8,14.15h5.65a7.65,7.65,0,0,0,1.78-.2,4.78,4.78,0,0,0,1.57-.65,3.43,3.43,0,0,0,1.13-1.2,3.63,3.63,0,0,0,.42-1.8A3.3,3.3,0,0,0,151,8.6a3.42,3.42,0,0,0-1.23-1.13A6.07,6.07,0,0,0,148,6.9a9.9,9.9,0,0,0-1.85-.18h-5.3Zm0,14.65h7a8.27,8.27,0,0,0,1.83-.2,4.67,4.67,0,0,0,1.67-.7,3.93,3.93,0,0,0,1.23-1.3,3.8,3.8,0,0,0,.47-1.95,3.16,3.16,0,0,0-.62-2,4,4,0,0,0-1.58-1.18,8.23,8.23,0,0,0-2-.55,15.12,15.12,0,0,0-2.05-.15h-5.9Z"/></g></g></svg>
"This product uses the TMDB API but is not endorsed or certified by TMDB."

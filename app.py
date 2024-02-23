from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, jsonify, send_file
from sqlalchemy import create_engine, Column, String, Float, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
import os
import random
import logging
import string
import requests
from datetime import timedelta
import bisect
import sqlite3
from urllib.parse import quote, quote_plus
import json
import pandas as pd
from spotipy.exceptions import SpotifyException


logging.basicConfig(filename='app.log', level=logging.DEBUG)

app = Flask(__name__)

app.secret_key = "150206wijprbd"
app.config['SESSION_COOKIE_NAME'] = 'Melo'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
TOKEN_INFO = "token_info"

Base = declarative_base()

class DB_User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True)
    genre_rec = Column(JSON)
    liked_tracks = Column(JSON)
    disliked_tracks = Column(JSON)
    has_playlist = Column(Boolean)
    total_danceability = Column(Float)
    token_info = Column(String)
    genres = Column(JSON)
    playlist_id = Column(String)
    pgenre = Column(JSON)

class MeloDB:
    def __init__(self):
        self.engine = create_engine('sqlite:///Mélo.db')
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)

    def deletedb(self):
        try:
            Base.metadata.drop_all(self.engine)
            Base.metadata.create_all(self.engine)
            logging.info("Database deleted and recreated successfully.")
        except Exception as e:
            logging.error(f"Error deleting and recreating the database: {str(e)}")

    def add_user(self, user):
        session = self.Session()
        try:
            user_db = DB_User(
                id=user.id,
                genre_rec=json.dumps(user.genre_rec),
                liked_tracks=json.dumps(user.liked_tracks),
                disliked_tracks=json.dumps(user.disliked_tracks),
                has_playlist=user.has_playlist,
                total_danceability=user.total_danceability,
                token_info=json.dumps(user.token_info) if user.token_info else "{}",
                genres=json.dumps(user.genres),
                playlist_id=user.playlist_id,
                pgenre=json.dumps(user.pgenre),
            )
            session.add(user_db)
            session.commit()
            logging.info(f"User {user.id} added successfully.")
        except Exception as e:
            logging.error(f"Error adding user {user.id}: {str(e)}")
            session.rollback()
        finally:
            session.close()

    def update_user(self, user):
        session = self.Session()
        try:
            user_db = session.query(DB_User).filter_by(id=user.id).first()
            if user_db:
                user_db.genre_rec = json.dumps(user.genre_rec)
                user_db.liked_tracks = json.dumps(user.liked_tracks)
                user_db.disliked_tracks = json.dumps(user.disliked_tracks)
                user_db.has_playlist = user.has_playlist
                user_db.total_danceability = user.total_danceability
                user_db.token_info = json.dumps(user.token_info)
                user_db.genres = json.dumps(user.genres)
                user_db.playlist_id = user.playlist_id
                user_db.pgenre = json.dumps(user.pgenre)
                session.commit()
                logging.info(f"User {user.id} updated successfully.")
        except Exception as e:
            logging.error(f"Error updating user {user.id}: {str(e)}")
            session.rollback()
        finally:
            session.close()

    def create_playlist(self, user_id, access_token):
        # Check if the user already has a playlist
        user_db = self.get_user(user_id)
        if user_db and user_db.has_playlist:
            return user_db.playlist_id
        else:
            # Create a new playlist for the user
            sp = spotipy.Spotify(auth=access_token)
            playlist_name = "Mélo"   
            playlist_description = "A place to save your new songs!"   
            try:
                playlist = sp.user_playlist_create(user_id, playlist_name, public=False, description=playlist_description)
                logging.info(f"Playlist created for user {user_id}: {playlist}")

                # Update the user's playlist ID and set has_playlist to true
                user_db.playlist_id = playlist['id']
                user_db.has_playlist = True

                # Commit the changes to the database
                self.Session().commit()  # Use the correct session object for committing

                logging.info(f"Playlist ID updated for user {user_id} to {playlist['id']}.")
                return playlist['id']
            except spotipy.exceptions.SpotifyException as e:
                logging.error(f"Spotify API error creating playlist for user {user_id}: {str(e)}")
            except Exception as e:
                logging.error(f"Unexpected error creating playlist for user {user_id}: {str(e)}")
                self.Session().rollback()  # Use the correct session object for rolling back
            return None

    def get_user(self, user_id):
        session = self.Session()
        user_db = session.query(DB_User).filter_by(id=user_id).first()
        if user_db:
            # Convert the DB_User object to a User object
            user = User(
                id=user_db.id,
                genre_rec=json.loads(user_db.genre_rec),
                liked_tracks=json.loads(user_db.liked_tracks),
                disliked_tracks=json.loads(user_db.disliked_tracks),
                has_playlist=user_db.has_playlist,
                total_danceability=user_db.total_danceability,
                token_info=json.loads(user_db.token_info) if user_db.token_info else {},
                genres=json.loads(user_db.genres),
                playlist_id=user_db.playlist_id,
                pgenre=json.loads(user_db.pgenre),
            )
            return user
        return None

    def set_playlist_id(self, user_id, playlist_id):
        current_user = self.get_user(user_id)
        if current_user:
            current_user.playlist_id = playlist_id
            self.update_user(current_user)

    def add_liked_track(self, user_id, track_id):
        current_user = self.get_user(user_id)
        if current_user:
            current_liked_tracks = current_user.liked_tracks
            if track_id not in current_liked_tracks:
                current_liked_tracks.append(track_id)
                current_user.liked_tracks = json.dumps(current_liked_tracks)

                if current_user.has_playlist and current_user.playlist_id:
                    sp = spotipy.Spotify(auth=current_user.token_info['access_token'])
                    try:
                        sp.playlist_add_items(current_user.playlist_id, [track_id])
                    except spotipy.exceptions.SpotifyException as e:
                        logging.error(f"Error adding track to playlist: {str(e)}")

                self.update_user(current_user)
                logging.info(f"Liked track {track_id} added for user {user_id}")
            else:
                logging.info(f"Track {track_id} is already in the liked tracks list for user {user_id}")
        else:
            logging.error(f"User {user_id} not found")

    def add_disliked_track(self, user_id, track_id):
        current_user = self.get_user(user_id)
        if current_user:
            current_disliked_tracks = current_user.disliked_tracks
            if track_id not in current_disliked_tracks:
                current_disliked_tracks.append(track_id)
                current_user.disliked_tracks = json.dumps(current_disliked_tracks)
                try:
                    self.update_user(current_user)
                    logging.info(f"Disliked track {track_id} added for user {user_id}")
                except Exception as e:
                    logging.error(f"Error updating disliked tracks for user {user_id}: {str(e)}")
            else:
                logging.info(f"Track {track_id} is already in the disliked tracks list for user {user_id}")
        else:
            logging.error(f"User {user_id} not found")

    def update_total_danceability(self, user_id, new_danceability):
        current_user = self.get_user(user_id)
        if current_user:
            current_user.total_danceability = new_danceability
            self.update_user(current_user)

    def update_genres(self, user_id, new_genres):
        current_user = self.get_user(user_id)
        if current_user:
            current_user.genres = new_genres
            self.update_user(current_user)

    def update_token_info(self, user_id, token_info):
        session = self.Session()
        try:
            user_db = session.query(DB_User).filter_by(id=user_id).first()
            if user_db:
                user_db.token_info = json.dumps(token_info)
                session.commit()
                logging.info(f"Token info updated for user {user_id} successfully.")
        except Exception as e:
            logging.error(f"Error updating token info for user {user_id}: {str(e)}")
            session.rollback()
        finally:
            session.close()

    def user_has_playlist(self, user_id):
        session = self.Session()
        user_db = session.query(DB_User).filter_by(id=user_id).first()
        return user_db and user_db.has_playlist

    def export_users_to_excel(self):
        session = self.Session()
        users = session.query(DB_User).all()
        data = [user.__dict__ for user in users]
        for user_dict in data:
            user_dict['genre_rec'] = json.loads(user_dict['genre_rec'])
            user_dict['liked_tracks'] = json.loads(user_dict['liked_tracks'])
            user_dict['disliked_tracks'] = json.loads(user_dict['disliked_tracks'])
            user_dict['genres'] = json.loads(user_dict['genres'])
            user_dict['pgenre'] = json.loads(user_dict['pgenre'])
            # Check if token_info is None before trying to deserialize it
            if user_dict['token_info'] is not None:
                user_dict['token_info'] = json.loads(user_dict['token_info'])
            else:
                user_dict['token_info'] = {}  # Provide a default empty dict or another appropriate value
        df = pd.DataFrame(data)
        filename = "users_export.xlsx"
        with pd.ExcelWriter(filename) as writer:
            df.to_excel(writer, index=False)
        return send_file(filename, as_attachment=True)

class User:
    def __init__(self, id, liked_tracks=[], disliked_tracks=[], has_playlist=False, token_info=None, playlist_id=None, genres=None, genre_rec=None, pgenre=None, total_danceability=0.0):
        self.id = id
        self.liked_tracks = liked_tracks
        self.disliked_tracks = disliked_tracks
        self.has_playlist = has_playlist
        self.token_info = token_info
        self.playlist_id = playlist_id
        self.genres = genres if genres is not None else ["R&B", "Soul", "EDM", "Reggaeton", "Pop-Rock", "K-Pop", "Hip Hop", "Pop", "Dancehall","Reggae", "Electronic", "Disco", "Dance-Pop", "Folk", "Pop-Rock","Gospel", "Teen Pop","City Pop", "Indie Pop", "Bedroom Pop", "Corridos Tumbados", "Soft Rock", "Folk-Pop", "Rock","Alternative R&B", "Neo-Soul", "Flamenco Fusion", "Art Pop", "Trip-Hop","Baroque Pop", "Indie Pop", "Pop Rap", "Country Rap", "Conscious Hip Hop","West Coast Hip Hop", "Jazz Rap", "Avant-Pop", "Emo Rock","J-Pop"]
        self.pgenre = pgenre if pgenre is not None else [1 / len(self.genres)] * (len(self.genres) -  1)
        self.genre_rec = genre_rec if genre_rec is not None else [1] * (len(self.genres) -  1)
        self.total_danceability = total_danceability

class SongRec:
    def __init__(self, db_user, action, genre_id, danceability, track_id):
        self.db_user = db_user
        self.action = str(action)
        self.genre_id = int(genre_id)
        self.danceability = float(danceability)
        self.track_id = str(track_id)

    def process_song(self):
        try:
            app.logger.debug(f"Initializing Spotipy client with access token: {self.db_user.token_info['access_token']}")
            db = MeloDB()
            if self.action == "like" or self.action == "super":
                if self.action == "super":
                    self.db_user.genre_rec[self.genre_id] +=  1
                self.db_user.genre_rec[self.genre_id] +=  1

                total_index = sum(self.db_user.genre_rec)
                app.logger.debug(f"Total index: {total_index}, genre_rec: {self.db_user.genre_rec}")

                self.db_user.pgenre[self.genre_id] = self.db_user.genre_rec[self.genre_id] / total_index
                for q in range(len(self.db_user.genre_rec)-1):
                    if q != self.genre_id:
                        self.db_user.pgenre[q] = self.db_user.genre_rec[q] / total_index
                        app.logger.debug(f"pgenre[{q}]: {self.db_user.pgenre[q]}")

                if len(self.db_user.liked_tracks) ==   0:
                    self.db_user.total_danceability = self.danceability
                else:
                    if self.action == "like":
                        self.db_user.total_danceability = (self.db_user.total_danceability * (len(self.db_user.liked_tracks) -   1) + self.danceability) / len(self.db_user.liked_tracks)
                    if self.action == "super":
                        self.db_user.total_danceability = (self.db_user.total_danceability * (len(self.db_user.liked_tracks) -   1) + (self.danceability *   2)) / (len(self.db_user.liked_tracks)+1)

                db.add_liked_track(self.db_user.id, self.track_id)
                app.logger.debug(f"like done")

            if self.action == "dislike":
                if self.db_user.genre_rec[self.genre_id] >  1:
                    self.db_user.genre_rec[self.genre_id] -=  1

                    total_index = sum(self.db_user.genre_rec)
                    self.db_user.pgenre[self.genre_id] = self.db_user.genre_rec[self.genre_id] / total_index
                    for q in range(len(self.db_user.genre_rec)):
                        if q != self.genre_id:
                            self.db_user.pgenre[q] = self.db_user.genre_rec[q] / total_index
                    app.logger.debug(f"dislike done")

                db.add_disliked_track(self.db_user.id, self.track_id)

            app.logger.debug(f"After processing action, genre_rec: {self.db_user.genre_rec}, pgenre: {self.db_user.pgenre}")
            db.update_user(self.db_user)
            app.logger.info("User updated in the database")
            app.logger.debug(f"Processed song with track ID: {self.track_id}")

            return jsonify({'status': 'success'})

        except SpotifyException as e:
            app.logger.error(f"Spotify API error processing song with track ID {self.track_id}: {str(e)}")
            raise
        except Exception as e:
            app.logger.error(f"Unexpected error processing song with track ID {self.track_id}: {str(e)}")
            raise


# All app routes

@app.route('/getTracks', methods=['GET','POST'])
def getTracks():
    user_data = session['user']
    db = MeloDB()
    db_user = db.get_user(user_data['id'])

    if db_user is None:
        new_user = User(id=user_data['id'])
        db.add_user(new_user)
        db_user = new_user

    # Check if pgenre is a JSON string and parse it into a list of integers
    if isinstance(db_user.pgenre, str):
        try:
            db_user.pgenre = json.loads(db_user.pgenre)
        except json.JSONDecodeError:
            # If parsing fails, log an error and reset pgenre to a default value
            logging.error(f"Failed to parse pgenre for user {user_data['id']}: {db_user.pgenre}")
            db_user.pgenre = [1] * (len(db_user.genres) -   1)
    elif not isinstance(db_user.pgenre, list):
        # If pgenre is neither a string nor a list, reset it to a default value
        logging.error(f"Invalid pgenre type for user {user_data['id']}: {type(db_user.pgenre)}")
        db_user.pgenre = [1] * (len(db_user.genres) -   1)

    token_info = get_token()
    sp = spotipy.Spotify(auth=token_info['access_token'])

    tracks = None
    track_details = {}

    total_sum = sum(db_user.pgenre)
    random_value = random.uniform(0, total_sum)

    max_attempts =   300
    attempt_count =   0

    while attempt_count < max_attempts:
        
        offset = random.randint(0,999)
        char = random.choice('abcdefghijklmnopqrstuvwxyz1234567890')
        possibility = random.randint(1,   2)
        if possibility ==   1:
            query = char + "%"
        elif possibility ==   2:
            query = "%" + char + "%"
        
        cumulative_distribution = [sum(db_user.pgenre[:i+1]) for i in range(len(db_user.pgenre))]
        picked_genre = db_user.genres[bisect.bisect(cumulative_distribution, random_value) -   1]

        char = quote(char)  # URL-encode the character
        query = char + "%"
        genre_filter = f"genre:{quote(picked_genre)}"
        combined_query = f"({query})+AND+({genre_filter})"

        results = sp.search(q=combined_query, type='track', limit=1, offset=offset)
        tracks = results['tracks']['items']

        if not tracks:
            attempt_count +=   1
            continue

        liked_tracks = db_user.liked_tracks
        disliked_tracks = db_user.disliked_tracks

        if not any(tracks['id'] in (liked_track['id'], disliked_track['id']) for liked_track in liked_tracks for disliked_track in disliked_tracks):            
            random_track = random.choice(tracks)

            artist_id = random_track['artists'][0]['id']
            artist = sp.artist(artist_id)
            artist_genres = artist['genres']

            common_genres = set(artist_genres).intersection(set(db_user.genres))

            if common_genres:
                picked_genre = max(common_genres, key=lambda genre: db_user.genres.count(genre))
                genre_id = db_user.genres.index(picked_genre)
            else:
                picked_genre = random.choice(db_user.genres)
                genre_id = db_user.genres.index(picked_genre)

            audio_features = sp.audio_features([random_track['id']])[0]
            danceability = audio_features['danceability']

            if len(liked_tracks) >=   20 and abs(danceability - db_user.total_danceability) >   0.2:
                logging.debug('Danceability threshold exceeded for track %s', random_track['id'])  # Log danceability threshold exceeded
                attempt_count +=   1
                continue

            track_name = random_track['name']
            artist_name = random_track['artists'][0]['name']
            album_name = random_track['album']['name']
            album_image = random_track['album']['images'][0]['url']
            track_id = random_track['id']

            # Ensure genre_rec is a list of integers and is in sync with genres
            try:
                db_user.genre_rec = [int(rec) for rec in db_user.genre_rec]
            except ValueError:
                # If genre_rec is not a valid list of integers, reset it to a default value
                db_user.genre_rec = [1] * (len(db_user.genres) -   1)

            # Check if picked_genre is in the user's genres and get its index
            if picked_genre not in db_user.genres:
                db_user.genres.append(picked_genre)
                db_user.genre_rec.append(1)  # Add a new entry for the new genre
                genre_id = len(db_user.genres) -   1  # The index of the newly added genre
            else:
                genre_id = db_user.genres.index(picked_genre)

            # Ensure that genre_rec has the same length as genres
            while len(db_user.genre_rec) < len(db_user.genres):
                db_user.genre_rec.append(1)  # Add a default entry for the new genre

            # Update the user's genre_rec in the database
            db.update_user(db_user)

            track_details = {
                'trackName': track_name,
                'artistName': artist_name,
                'albumName': album_name,
                'albumImage': album_image,
                'trackId': track_id,
                'trackUri': random_track['uri'],
                'genre': picked_genre,
                'danceability': danceability,
                'genreId': genre_id,
                'playlistId': db_user.playlist_id,
            }

            tracks = [random_track]
            break

        else:
            logging.debug('Track %s is already liked or disliked', tracks[0]['id'])  # Log duplicate track
            attempt_count +=   1
            tracks = None

    if track_details:
        logging.info('Suitable track found: %s', track_details)  # Log successful track selection
        session['access_token'] = token_info['access_token']
        accessing = session['access_token']
        return render_template('getTracks.html', track_details=track_details, access_token=accessing)
    else:
        logging.warning('No suitable track found after %d attempts', max_attempts)  # Log when no track is found
        return "No suitable track found after 300 attempts",   404

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/deletedb', methods=['GET'])
def deletedb():
    db = MeloDB()
    db.deletedb()
    db = MeloDB()
    return redirect(url_for('index'))

@app.route('/login')
def login():
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/redirectpage')
def redirectPage():
    sp_oauth = create_spotify_oauth()
    code = request.args.get('code')  # Get the authorization code from the query parameters
    token_info = sp_oauth.get_access_token(code)  # Pass the authorization code to get_access_token
    if token_info:
        session[TOKEN_INFO] = token_info
        sp = spotipy.Spotify(auth=token_info['access_token'])
        user_info = sp.current_user()
        user_id = user_info['id']

        # Ensure user_data is a dictionary before assigning values
        user_data = session.get('user', {})
        user_data['id'] = user_id
        session['user'] = user_data

        db = MeloDB()
        db_user = db.get_user(user_id)

        if db_user is None:
            new_user = User(id=user_id)   
            db.add_user(new_user)
            db_user = new_user

        # Check if the user already has a playlist
        if not db_user.has_playlist:
            # Create a new playlist for the user
            playlist_id = db.create_playlist(user_id, token_info['access_token'])
            if playlist_id:
                # Update the user's playlist ID and set has_playlist to true
                db_user.playlist_id = playlist_id
                db_user.has_playlist = True

        # Save the token_info in the user's database entry
        db_user.token_info = token_info
        db.update_user(db_user)

        return redirect(url_for('getTracks', _external=True))
    else:
        # Handle the case where token_info is None (e.g., authorization failed)
        return "Authorization failed",  400

@app.route('/logout')
def logout():
    try:
        # Retrieve the access token from the session
        token_info = session.get(TOKEN_INFO)
        if token_info:
            access_token = token_info['access_token']
            # Revoke the access token if it exists
            revoke_access_token(access_token)
            logging.info(f"Access token for user {session.get('user', {}).get('id')} revoked successfully.")
        else:
            logging.warning("No access token found in session.")

        # Clear session data
        session.pop('user', None)
        session.pop(TOKEN_INFO, None)
        # Add any other session data you want to clear

        # Redirect the user to the login page
        return redirect(url_for('index'))
    except Exception as e:
        logging.error(f"Error during logout: {str(e)}")
        return "An error occurred during logout.",   500

@app.route('/export_users', methods=['GET'])
def export_users():
    melo_db = MeloDB()
    return melo_db.export_users_to_excel()

@app.route('/play', methods=['POST'])
def play():
    token_info = get_token()

    if not token_info:
        return jsonify({'error': 'No access token found or failed to refresh'}),  401

    sp = spotipy.Spotify(auth=token_info['access_token'])
    try:
        # Get the current user's devices
        devices = sp.devices()
        # Select the first available device
        device_id = devices['devices'][0]['id'] if devices['devices'] else None
        if device_id:
            # Get the current playback
            current_playback = sp.current_playback()
            if current_playback:
                current_track_uri = current_playback['item']['uri']
            else:
                current_track_uri = None

            # Get the trackUri from the request
            data = request.get_json()
            track_uri = data.get('trackUri')

            # Check if the current track is the same as the trackUri we want to play
            if current_track_uri != track_uri:
                # If it's not the same, start playback of the new trackUri
                sp.start_playback(device_id=device_id, uris=[track_uri])
                return jsonify({'message': 'Track started playing'}),  200
            else:
                # If it's the same, toggle playback
                if current_playback['is_playing']:
                    sp.pause_playback()
                    return jsonify({'message': 'Track paused'}),  200
                else:
                    sp.start_playback(device_id=device_id)
                    return jsonify({'message': 'Track started playing'}),  200
        else:
            return jsonify({'error': 'No active device found'}),  404
    except spotipy.exceptions.SpotifyException as e:
        return jsonify({'error': str(e)}),  500
    except Exception as e:
        logging.error(f"Unexpected error during playback: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}),  500

@app.route('/pause', methods=['POST'])
def pause():
    token_info = session.get(TOKEN_INFO)

    if not token_info:
        return jsonify({'error': 'No access token found'}),  401

    sp = spotipy.Spotify(auth=token_info['access_token'])
    try:
        sp.pause_playback()
        return jsonify({'message': 'Track paused'}),  200
    except spotipy.exceptions.SpotifyException as e:
        return jsonify({'error': str(e)}),  500

@app.route('/replay', methods=['POST'])
def replay():
    data = request.get_json()
    track_uri = data.get('trackUri')
    token_info = get_token()

    if not token_info:
        return jsonify({'error': 'No access token found or failed to refresh'}),   401

    sp = spotipy.Spotify(auth=token_info['access_token'])
    try:
        # Get the current user's devices
        devices = sp.devices()
        # Select the first available device
        device_id = devices['devices'][0]['id'] if devices['devices'] else None
        if device_id:
            # Start playback on the selected device from the beginning
            sp.start_playback(device_id=device_id, uris=[track_uri])
            return jsonify({'message': 'Track replayed from the beginning'}),   200
        else:
            return jsonify({'error': 'No active device found'}),   404
    except spotipy.exceptions.SpotifyException as e:
        return jsonify({'error': str(e)}),   500
    except Exception as e:
        logging.error(f"Unexpected error during playback: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}),   500

@app.route('/change_action', methods=['POST'])
def change_action():
    try:
        data = request.get_json()

        # Validate the data
        if not data or not all(key in data for key in ['trackId', 'action', 'genreId', 'danceability', 'access_token']):
            app.logger.error(f"Missing required fields in request data: {data}")
            return jsonify({'error': 'Missing required fields'}),   400

        track_id = str(data.get('trackId'))
        app.logger.debug(f"trackId: {track_id}, type: {type(track_id)}")
        action = data.get('action')
        genre_id = int(data.get('genreId'))  # Convert to integer
        danceability = float(data.get('danceability'))  # Convert to float
        access_token = str(data.get('access_token'))  # Convert to string

        # Check if the access_token is present
        if not access_token:
            app.logger.error(f"Access token is missing in request data: {data}")
            return jsonify({'error': 'Access token is missing'}),   400

        # Log the received data for debugging
        app.logger.debug(f"Received data: {data}")

        # Retrieve the current user
        user_data = session['user']
        db = MeloDB()
        db_user = db.get_user(user_data['id'])

        # Process the song based on the action
        song_rec = SongRec(db_user, action, genre_id, danceability, track_id)
        song_rec.process_song()

        # Update the user's genre_rec in the database
        db.update_user(db_user)

        # Return a success response
        return jsonify({'success': True}),   200
    except ValueError as e:
        app.logger.error(f"Invalid data type in request data: {str(e)}")
        return jsonify({'error': 'Invalid data type in request data'}),   400
    except Exception as e:
        app.logger.error(f"Error processing action: {str(e)}")
        return jsonify({'error': 'An error occurred while processing the action'}),   500

def create_spotify_oauth():
    return SpotifyOAuth(
        client_id="1fca3948a7e34ad688a7c5ef08ed9b3d",
        client_secret="d324d81ed760403e80dc5fd83a7f900d",
        redirect_uri="http://localhost:5000/redirectpage",
        scope = "user-library-read user-read-playback-state user-modify-playback-state streaming app-remote-control user-top-read user-read-private user-read-email playlist-modify-private user-read-currently-playing user-read-playback-position user-read-recently-played"
    )

def revoke_access_token(access_token):
    # The URL to revoke the access token
    revoke_url = "https://accounts.spotify.com/api/token/revoke"
    # The headers required for the request
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    # Make the POST request to revoke the access token
    response = requests.post(revoke_url, headers=headers)
    if response.status_code ==  200:
        logging.info(f"Access token revoked successfully.")
    elif response.status_code ==  404:
        logging.error(f"Failed to revoke access token: Endpoint not found. Response content: {response.content}")
    else:
        logging.error(f"Failed to revoke access token: Unexpected response. Status code: {response.status_code}, Response content: {response.content}")

def get_token():    
    token_info = session.get(TOKEN_INFO, None)
    if not token_info:
        return None
    now = int(time.time())
    is_expired = token_info['expires_at'] - now <  60
    if is_expired:
        sp_oauth = create_spotify_oauth()
        try:
            token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
            logging.info(f"Access token refreshed: {token_info}")
            # Update the session with the new token information
            session[TOKEN_INFO] = token_info
        except Exception as e:
            logging.error(f"Failed to refresh access token: {str(e)}")
            return None
    return token_info

if __name__ == '__main__':
   app.run(debug=True)
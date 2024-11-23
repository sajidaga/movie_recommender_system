from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
from surprise import Dataset, Reader, SVD
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import CountVectorizer
import numpy as np
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Global variables for models and data
users = None
movies = None
ratings = None
model = None
vectorizer = None
genre_similarity = None

# Load datasets with proper error handling
def load_datasets():
    global users, movies, ratings, model, vectorizer, genre_similarity
    
    logger.info("Loading datasets...")
    try:
        # Load or create users dataset
        if os.path.exists('users.csv'):
            users = pd.read_csv('users.csv')
            logger.info(f"Loaded {len(users)} users")
        else:
            users = pd.DataFrame(columns=['userId', 'username', 'password', 'isAdmin'])
            users.to_csv('users.csv', index=False)
            logger.info("Created new users dataset")

        # Load or create movies dataset
        if os.path.exists('movies.csv'):
            movies = pd.read_csv('movies.csv')
            logger.info(f"Loaded {len(movies)} movies")
        else:
            movies = pd.DataFrame(columns=['movieId', 'title', 'genres'])
            movies.to_csv('movies.csv', index=False)
            logger.info("Created new movies dataset")

        # Load or create ratings dataset
        if os.path.exists('ratings.csv'):
            ratings = pd.read_csv('ratings.csv')
            logger.info(f"Loaded {len(ratings)} ratings")
        else:
            ratings = pd.DataFrame(columns=['userId', 'movieId', 'rating'])
            ratings.to_csv('ratings.csv', index=False)
            logger.info("Created new ratings dataset")

        # Initialize models if we have data
        if not movies.empty:
            # Initialize CountVectorizer and genre similarity matrix
            movies['genres'] = movies['genres'].fillna('')
            vectorizer = CountVectorizer()
            genre_matrix = vectorizer.fit_transform(movies['genres'])
            genre_similarity = cosine_similarity(genre_matrix)
            logger.info("Initialized genre similarity matrix")

        if not ratings.empty:
            # Initialize and train SVD model
            reader = Reader(rating_scale=(0.5, 5))
            data = Dataset.load_from_df(ratings[['userId', 'movieId', 'rating']], reader)
            trainset = data.build_full_trainset()
            model = SVD()
            model.fit(trainset)
            logger.info("Trained SVD model")

    except Exception as e:
        logger.error(f"Error loading datasets: {str(e)}")
        raise

# Load datasets on startup
load_datasets()

def recommend_for_new_user(user_id, top_n=5):
    logger.info(f"Generating recommendations for new user {user_id}")
    try:
        if movies.empty:
            return []

        # Get most popular genres
        genre_count = movies['genres'].str.split('|').explode().value_counts()
        preferred_genres = genre_count.head(3).index.tolist()
        
        recommended_movies = []
        for genre in preferred_genres:
            genre_movies = movies[movies['genres'].str.contains(genre, na=False)]
            for _, movie in genre_movies.iterrows():
                recommended_movies.append({
                    'movieId': int(movie['movieId']),
                    'title': str(movie['title']),
                    'genres': str(movie['genres'])
                })
        
        # Remove duplicates and return top N
        seen = set()
        unique_recommendations = []
        for movie in recommended_movies:
            if movie['movieId'] not in seen:
                seen.add(movie['movieId'])
                unique_recommendations.append(movie)
                if len(unique_recommendations) >= top_n:
                    break
                    
        return unique_recommendations
    except Exception as e:
        logger.error(f"Error in recommend_for_new_user: {str(e)}")
        return []

def recommend_for_existing_user(user_id, top_n=5):
    logger.info(f"Generating recommendations for existing user {user_id}")
    try:
        if model is None:
            return recommend_for_new_user(user_id, top_n)

        user_ratings = ratings[ratings['userId'] == user_id]
        rated_movie_ids = user_ratings['movieId'].values
        
        # Get all movie IDs except those already rated
        all_movie_ids = movies['movieId'].values
        unrated_movie_ids = [mid for mid in all_movie_ids if mid not in rated_movie_ids]
        
        if not unrated_movie_ids:
            return recommend_for_new_user(user_id, top_n)

        # Predict ratings for unrated movies
        predictions = []
        for movie_id in unrated_movie_ids:
            try:
                predicted_rating = model.predict(user_id, movie_id).est
                predictions.append((movie_id, predicted_rating))
            except Exception as e:
                logger.warning(f"Error predicting rating for movie {movie_id}: {str(e)}")
                continue
        
        # Sort by predicted rating and get top N
        recommendations = sorted(predictions, key=lambda x: x[1], reverse=True)[:top_n]
        
        recommended_movies = []
        for movie_id, rating in recommendations:
            movie = movies[movies['movieId'] == movie_id].iloc[0]
            recommended_movies.append({
                'movieId': int(movie_id),
                'title': str(movie['title']),
                'genres': str(movie['genres']),
                'predicted_rating': float(rating)
            })
        
        return recommended_movies
    except Exception as e:
        logger.error(f"Error in recommend_for_existing_user: {str(e)}")
        return []

def hybrid_recommend(user_id, top_n=5):
    logger.info(f"Starting hybrid recommendation for user {user_id}")
    try:
        # Check if user exists and has ratings
        user_ratings = ratings[ratings['userId'] == user_id]
        if user_ratings.empty:
            return recommend_for_new_user(user_id, top_n)
        else:
            return recommend_for_existing_user(user_id, top_n)
    except Exception as e:
        logger.error(f"Error in hybrid_recommend: {str(e)}")
        return []

@app.route('/register', methods=['POST'])
def register():
    try:
        global users
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        is_admin = data.get('isAdmin', False)

        if not username or not password:
            return jsonify({'message': 'Username and password are required'}), 400

        if username in users['username'].values:
            return jsonify({'message': 'Username already exists'}), 400

        new_user_id = users['userId'].max() + 1 if not users.empty else 1
        new_user = pd.DataFrame([[new_user_id, username, password, is_admin]], 
                              columns=['userId', 'username', 'password', 'isAdmin'])
        
        
        users = pd.concat([users, new_user], ignore_index=True)
        users.to_csv('users.csv', index=False)
        
        return jsonify({'message': 'User registered successfully!', 'userId': int(new_user_id)}), 200
    except Exception as e:
        logger.error(f"Error in register: {str(e)}")
        return jsonify({'message': 'Registration failed'}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'message': 'Username and password are required'}), 400

        user = users[(users['username'] == username) & (users['password'] == password)]
        if not user.empty:
            user_id = int(user['userId'].iloc[0])
            is_admin = bool(user['isAdmin'].iloc[0])
            return jsonify({
                'userId': user_id,
                'isAdmin': is_admin,
                'message': 'Login successful'
            }), 200
        return jsonify({'message': 'Invalid credentials'}), 401
    except Exception as e:
        logger.error(f"Error in login: {str(e)}")
        return jsonify({'message': 'Login failed'}), 500

@app.route('/recommend/<int:user_id>', methods=['GET'])
def get_recommendations(user_id):
    try:
        logger.info(f"Fetching recommendations for user {user_id}")
        if user_id not in users['userId'].values:
            return jsonify({'message': 'User not found'}), 404

        recommendations = hybrid_recommend(user_id)
        if not recommendations:
            return jsonify({
                'recommendations': [],
                'message': 'No recommendations available at this time'
            }), 200

        return jsonify({'recommendations': recommendations}), 200
    except Exception as e:
        logger.error(f"Error in get_recommendations: {str(e)}")
        return jsonify({'message': f'Error fetching recommendations: {str(e)}'}), 500

@app.route('/admin/add-movie', methods=['POST'])
def add_movie():
    try:
        data = request.get_json()
        user_id = data.get('userId')
        
        # Verify admin status
        user = users[users['userId'] == user_id]
        if user.empty or not user['isAdmin'].iloc[0]:
            return jsonify({'message': 'Unauthorized access'}), 403

        new_title = data.get('title')
        new_genres = data.get('genres')

        if not new_title or not new_genres:
            return jsonify({'message': 'Title and genres are required'}), 400

        global movies
        new_movie_id = movies['movieId'].max() + 1 if not movies.empty else 1
        new_movie = pd.DataFrame([[new_movie_id, new_title, new_genres]], 
                               columns=['movieId', 'title', 'genres'])
        
        movies = pd.concat([movies, new_movie], ignore_index=True)
        movies.to_csv('movies.csv', index=False)

        # Add a default rating to help with recommendations
        global ratings
        new_rating = pd.DataFrame({
            'userId': [0],
            'movieId': [new_movie_id],
            'rating': [3.0]
        })
        ratings = pd.concat([ratings, new_rating], ignore_index=True)
        ratings.to_csv('ratings.csv', index=False)
  
        # Reinitialize models
        load_datasets()

        return jsonify({
            'message': 'Movie added successfully!',
            'movieId': int(new_movie_id)
        }), 200
    except Exception as e:
        logger.error(f"Error in add_movie: {str(e)}")
        return jsonify({'message': f'Error adding movie: {str(e)}'}), 500

@app.route('/admin/delete-movie/<int:movie_id>', methods=['DELETE'])
def delete_movie(movie_id):
    try:
        global movies, ratings
        if movie_id not in movies['movieId'].values:
            return jsonify({'message': 'Movie not found'}), 404

        # Remove movie and its ratings
        movies = movies[movies['movieId'] != movie_id]
        ratings = ratings[ratings['movieId'] != movie_id]

        # Save updated datasets
        movies.to_csv('movies.csv', index=False)
        ratings.to_csv('ratings.csv', index=False)

        # Reinitialize models
        load_datasets()

        return jsonify({'message': 'Movie deleted successfully!'}), 200
    except Exception as e:
        logger.error(f"Error in delete_movie: {str(e)}")
        return jsonify({'message': f'Error deleting movie: {str(e)}'}), 500
    

    # Add these new routes to your Flask application

@app.route('/rate-movie', methods=['POST'])
def rate_movie():
    try:
        data = request.get_json()
        user_id = data.get('userId')
        movie_id = data.get('movieId')
        rating = data.get('rating')

        if not all([user_id, movie_id, rating]):
            return jsonify({'message': 'Missing required fields'}), 400

        if rating < 0.5 or rating > 5:
            return jsonify({'message': 'Rating must be between 0.5 and 5'}), 400

        global ratings
        # Update existing rating or add new one
        existing_rating = ratings[
            (ratings['userId'] == user_id) & 
            (ratings['movieId'] == movie_id)
        ]

        if not existing_rating.empty:
            # Update existing rating
            ratings.loc[
                (ratings['userId'] == user_id) & 
                (ratings['movieId'] == movie_id),
                'rating'
            ] = rating
        else:
            # Add new rating
            new_rating = pd.DataFrame({
                'userId': [user_id],
                'movieId': [movie_id],
                'rating': [rating]
            })
            ratings = pd.concat([ratings, new_rating], ignore_index=True)

        # Save to file
        ratings.to_csv('ratings.csv', index=False)
        
        # Retrain the model with new data
        load_datasets()

        return jsonify({'message': 'Rating submitted successfully'}), 200

    except Exception as e:
        logger.error(f"Error in rate_movie: {str(e)}")
        return jsonify({'message': f'Error submitting rating: {str(e)}'}), 500

@app.route('/user-ratings/<int:user_id>', methods=['GET'])
def get_user_ratings(user_id):
    try:
        if user_id not in users['userId'].values:
            return jsonify({'message': 'User not found'}), 404

        user_ratings = ratings[ratings['userId'] == user_id]
        if user_ratings.empty:
            return jsonify({'ratings': []}), 200

        # Merge with movies data to get movie titles
        rated_movies = user_ratings.merge(
            movies[['movieId', 'title', 'genres']], 
            on='movieId'
        )

        ratings_list = rated_movies.apply(
            lambda x: {
                'movieId': int(x['movieId']),
                'title': str(x['title']),
                'genres': str(x['genres']),
                'rating': float(x['rating'])
            }, 
            axis=1
        ).tolist()

        return jsonify({'ratings': ratings_list}), 200

    except Exception as e:
        logger.error(f"Error in get_user_ratings: {str(e)}")
        return jsonify({'message': f'Error fetching ratings: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
import React, { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [userId, setUserId] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [recommendations, setRecommendations] = useState([]);
  const [recommendationError, setRecommendationError] = useState("");
  const [message, setMessage] = useState("");
  const [newMovie, setNewMovie] = useState({ title: "", genres: "" });
  const [newMovieMessage, setNewMovieMessage] = useState("");
  const [adminLogin, setAdminLogin] = useState(false);
  const [userRatings, setUserRatings] = useState([]);
  const [ratingMessage, setRatingMessage] = useState("");

  // Star Rating Component
  const StarRating = ({ movieId, initialRating = 0, onRate }) => {
    const [rating, setRating] = useState(initialRating);
    
    const handleRatingChange = (newRating) => {
      setRating(newRating);
      onRate(movieId, newRating);
    };

    return (
      <div className="star-rating">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            onClick={() => handleRatingChange(star)}
            style={{
              color: star <= rating ? "gold" : "gray",
              background: "none",
              border: "none",
              cursor: "pointer",
              fontSize: "20px"
            }}
          >
            ★
          </button>
        ))}
      </div>
    );
  };

  // Fetch user's ratings
  const getUserRatings = async () => {
    if (userId) {
      try {
        const response = await axios.get(
          `http://127.0.0.1:5000/user-ratings/${userId}`
        );
        setUserRatings(response.data.ratings || []);
      } catch (error) {
        console.error("Error fetching user ratings:", error);
      }
    }
  };

  // Submit a rating
  const submitRating = async (movieId, rating) => {
    try {
      const response = await axios.post("http://127.0.0.1:5000/rate-movie", {
        userId,
        movieId,
        rating: parseFloat(rating)
      });
      setRatingMessage(response.data.message);
      getUserRatings(); // Refresh ratings
      getRecommendations(); // Refresh recommendations
    } catch (error) {
      setRatingMessage(error.response?.data?.message || "Error submitting rating");
    }
  };

  // Fetch user ratings on login
  useEffect(() => {
    if (isLoggedIn && !isAdmin) {
      getUserRatings();
    }
  }, [isLoggedIn]);

  // Login function
  const loginUser = async () => {
    if (username && password) {
      try {
        const response = await axios.post("http://127.0.0.1:5000/login", {
          username,
          password,
        });
        setMessage(response.data.message);
        setIsLoggedIn(true);
        setUserId(response.data.userId);
        setIsAdmin(response.data.isAdmin || false);
      } catch (error) {
        setMessage(error.response?.data?.message || "Invalid username or password.");
      }
    } else {
      setMessage("Please enter your username and password.");
    }
  };

  // Register function
  const registerUser = async () => {
    if (username && password) {
      try {
        const response = await axios.post("http://127.0.0.1:5000/register", {
          username,
          password,
          isAdmin: adminLogin,
        });
        setMessage(response.data.message);
      } catch (error) {
        setMessage("Error registering. Please try again later.");
      }
    } else {
      setMessage("Please provide a valid username and password.");
    }
  };

  // Get recommendations function
  const getRecommendations = async () => {
    if (userId) {
      try {
        setRecommendationError("");
        const response = await axios.get(
          `http://127.0.0.1:5000/recommend/${userId}`
        );

        if (response.data.recommendations && Array.isArray(response.data.recommendations)) {
          setRecommendations(response.data.recommendations);
          if (response.data.recommendations.length === 0) {
            setRecommendationError("No recommendations available at this time.");
          }
        } else {
          setRecommendationError("Invalid recommendation data received.");
        }
      } catch (error) {
        setRecommendationError(
          error.response?.data?.message || "Error fetching recommendations."
        );
        setRecommendations([]);
      }
    } else {
      setRecommendationError("User ID not available. Please try logging in again.");
    }
  };

  // Add movie function (admin only)
  const addNewMovie = async () => {
    if (!isAdmin) {
      setNewMovieMessage("Unauthorized. Only admins can add movies.");
      return;
    }

    if (newMovie.title && newMovie.genres) {
      try {
        const response = await axios.post("http://127.0.0.1:5000/admin/add-movie", {
          userId,
          title: newMovie.title,
          genres: newMovie.genres,
        });
        setNewMovieMessage(response.data.message);
        setNewMovie({ title: "", genres: "" });
      } catch (error) {
        setNewMovieMessage(
          error.response?.data?.message || "Error adding movie. Please try again later."
        );
      }
    } else {
      setNewMovieMessage("Please provide both title and genres.");
    }
  };

  // Recommendations Section Component
  const RecommendationsSection = () => (
    <div className="section">
      <h3>Your Recommendations</h3>
      <button onClick={getRecommendations} className="fetch-button">
        Fetch Recommendations
      </button>
      {recommendationError ? (
        <p className="error-message">{recommendationError}</p>
      ) : recommendations.length > 0 ? (
        <ul className="movie-list">
          {recommendations.map((movie) => (
            <li key={movie.movieId} className="movie-item">
              <div className="movie-info">
                <strong>{movie.title}</strong>
                <span className="movie-genres">{movie.genres}</span>
                {movie.predicted_rating && (
                  <span className="predicted-rating">
                    Predicted Rating: {movie.predicted_rating.toFixed(1)}
                  </span>
                )}
              </div>
              <StarRating
                movieId={movie.movieId}
                initialRating={userRatings.find(r => r.movieId === movie.movieId)?.rating || 0}
                onRate={submitRating}
              />
            </li>
          ))}
        </ul>
      ) : (
        <p>Click the button above to fetch recommendations.</p>
      )}
      {ratingMessage && <p className="rating-message">{ratingMessage}</p>}
    </div>
  );

  // User Ratings Section Component
  const UserRatingsSection = () => (
    <div className="section">
      <h3>Your Rated Movies</h3>
      {userRatings.length > 0 ? (
        <ul className="movie-list">
          {userRatings.map((movie) => (
            <li key={movie.movieId} className="movie-item">
              <div className="movie-info">
                <strong>{movie.title}</strong>
                <span className="movie-genres">{movie.genres}</span>
                <span className="current-rating">Current Rating: {movie.rating}</span>
              </div>
              <StarRating
                movieId={movie.movieId}
                initialRating={movie.rating}
                onRate={submitRating}
              />
            </li>
          ))}
        </ul>
      ) : (
        <p>You haven't rated any movies yet.</p>
      )}
    </div>
  );

  return (
    <div className="App">
      <h1>Movie Recommendation System</h1>
      {!isLoggedIn ? (
        <div className="auth-container">
          <h2>Login</h2>
          <form className="auth-form">
            <div className="form-group">
              <label htmlFor="username">Username</label>
              <input
                type="text"
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="username-class"
              />
            </div>
            <div className="form-group">
              <label htmlFor="password">Password</label>
              <input
                type="password"
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>
                <input
                  type="checkbox"
                  checked={adminLogin}
                  onChange={(e) => setAdminLogin(e.target.checked)}
                />
                Admin Login
              </label>
            </div>
            <button type="button" onClick={loginUser} className="auth-button">
              Login
            </button>
            <button type="button" onClick={registerUser} className="auth-button">
              Register
            </button>
          </form>
          {message && <p className="message">{message}</p>}
        </div>
      ) : (
          <div className="main-content">
            <h2>Welcome, {username}!</h2>
            {isAdmin ? (
              <div className="admin-section">
                <p>You are logged in as an admin.</p>
                <div className="add-movie-form">
                  <h3>Add New Movie</h3>
                  <input
                    type="text"
                    placeholder="Movie Title"
                    value={newMovie.title}
                    onChange={(e) => setNewMovie({ ...newMovie, title: e.target.value })}
                  />
                  <input
                    type="text"
                    placeholder="Genres (separate with |)"
                    value={newMovie.genres}
                    onChange={(e) => setNewMovie({ ...newMovie, genres: e.target.value })}
                  />
                  <button onClick={addNewMovie}>Add Movie</button>
                  {newMovieMessage && <p>{newMovieMessage}</p>}
                </div>
              </div>
            ) : (
            <>
              <RecommendationsSection />
              <UserRatingsSection />
            </>
          )}
          <button
            onClick={() => {
              setIsLoggedIn(false);
              setUserId("");
              setUsername("");
              setPassword("");
              setIsAdmin(false);
              setRecommendations([]);
              setUserRatings([]);
              setMessage("");
            }}
            className="logout-button"
          >
            Logout
          </button>
        </div>
      )}
    </div>
  );
}

export default App;
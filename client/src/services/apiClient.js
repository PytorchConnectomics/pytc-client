import axios from 'axios';
import { message } from 'antd';

// API base URL
const API_BASE = `${process.env.REACT_APP_SERVER_PROTOCOL || 'http'}://${process.env.REACT_APP_SERVER_URL || 'localhost:4242'}`;

// Create axios instance
const apiClient = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
});

// Track if we've already shown auth error to prevent spam
let authErrorShown = false;

// Request interceptor: Add auth token to all requests
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: Handle 401 errors globally
apiClient.interceptors.response.use(
  (response) => {
    // Reset auth error flag on successful response
    authErrorShown = false;
    return response;
  },
  (error) => {
    // Handle 401 Unauthorized errors
    if (error.response?.status === 401) {
      // Prevent infinite error messages
      if (!authErrorShown) {
        authErrorShown = true;

        // Clear invalid token
        localStorage.removeItem('token');

        // Show user-friendly error
        message.error({
          content: 'Session expired. Please log in again.',
          duration: 5,
          key: 'auth-error', // Prevent duplicate messages
        });

        // Optionally: Redirect to login or emit event for UserContext
        // For now, we'll let the app handle it via the error
        console.warn('Authentication failed. Token cleared.');
      }

      // Return a rejected promise with a flag to prevent retries
      const authError = new Error('Authentication required');
      authError.isAuthError = true;
      authError.status = 401;
      return Promise.reject(authError);
    }

    // For other errors, pass through
    return Promise.reject(error);
  }
);

export default apiClient;

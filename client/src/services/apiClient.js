import axios from 'axios';

// API base URL
const API_BASE = `${process.env.REACT_APP_SERVER_PROTOCOL || 'http'}://${process.env.REACT_APP_SERVER_URL || 'localhost:4242'}`;

// Create axios instance without auth headers—app runs as guest by default.
const apiClient = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
});

export default apiClient;

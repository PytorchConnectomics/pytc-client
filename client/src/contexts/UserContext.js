import React, { createContext, useState, useCallback, useEffect } from 'react';

export const UserContext = createContext();

const API_URL = 'http://localhost:4242';

const UserContextWrapper = ({ children }) => {
  const [currentUser, setCurrentUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));

  const autoSignOut = useCallback(() => {
    setCurrentUser(null);
    setToken(null);
    localStorage.removeItem('token');
  }, []);

  // Check token on mount
  useEffect(() => {
    const checkUser = async () => {
      if (token) {
        try {
          const response = await fetch(`${API_URL}/users/me`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          if (response.ok) {
            const userData = await response.json();
            setCurrentUser({ ...userData, name: userData.username }); // Map username to name for compatibility
          } else {
            autoSignOut();
          }
        } catch (error) {
          console.error("Failed to fetch user", error);
          autoSignOut();
        }
      }
    };
    checkUser();
  }, [token, autoSignOut]);

  const signIn = async (username, password) => {
    try {
      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);

      const response = await fetch(`${API_URL}/token`, {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setToken(data.access_token);
        localStorage.setItem('token', data.access_token);
        // Fetch user details immediately
        const userRes = await fetch(`${API_URL}/users/me`, {
          headers: { Authorization: `Bearer ${data.access_token}` }
        });
        if (userRes.ok) {
          const userData = await userRes.json();
          setCurrentUser({ ...userData, name: userData.username });
          return true;
        }
      }
      return false;
    } catch (error) {
      console.error("Sign in error", error);
      return false;
    }
  };

  const signUp = async (username, password) => {
    try {
      const response = await fetch(`${API_URL}/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      if (response.ok) {
        // Auto sign in after registration
        return await signIn(username, password);
      }
      return false;
    } catch (error) {
      console.error("Sign up error", error);
      return false;
    }
  };

  return (
    <UserContext.Provider value={{ currentUser, setCurrentUser, signIn, signUp, autoSignOut }}>
      {children}
    </UserContext.Provider>
  );
};

export default UserContextWrapper;

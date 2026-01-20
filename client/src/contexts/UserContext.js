import React, { createContext, useState, useCallback, useEffect } from 'react';

export const UserContext = createContext();
const DEFAULT_USER = { username: 'guest', name: 'Guest' };

const UserContextWrapper = ({ children }) => {
  const [currentUser, setCurrentUser] = useState(DEFAULT_USER);

  const autoSignOut = useCallback(() => {
    setCurrentUser(DEFAULT_USER);
  }, []);

  // Auto-populate guest on mount
  useEffect(() => {
    setCurrentUser(DEFAULT_USER);
  }, []);

  const signIn = async () => {
    setCurrentUser(DEFAULT_USER);
    return true;
  };

  const signUp = async () => {
    setCurrentUser(DEFAULT_USER);
    return true;
  };

  return (
    <UserContext.Provider value={{ currentUser, setCurrentUser, signIn, signUp, autoSignOut }}>
      {children}
    </UserContext.Provider>
  );
};

export default UserContextWrapper;

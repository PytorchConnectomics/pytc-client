import React, { createContext, useState, useCallback } from 'react';
import localforage from 'localforage';

export const UserContext = createContext();

function hashPassword(password) {
  // Simple SHA-256 hash (prototype)
  return window.crypto.subtle.digest('SHA-256', new TextEncoder().encode(password)).then(buf =>
    Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('')
  );
// ...existing code...

export const UserProvider = ({ children }) => {
  const [currentUser, setCurrentUser] = useState(null);

  const autoSignOut = useCallback(() => {
    setCurrentUser(null);
  }, []);

  const signIn = async (name, password) => {
    const users = (await localforage.getItem('users')) || [];
    const hash = await hashPassword(password);
    const user = users.find(u => u.name === name && u.passwordHash === hash);
    if (user) {
      setCurrentUser(user);
      return true;
    }
    return false;
  };

  const signUp = async (name, password) => {
    const users = (await localforage.getItem('users')) || [];
    if (users.find(u => u.name === name)) return false;
    const hash = await hashPassword(password);
    const newUser = { id: Date.now(), name, passwordHash: hash, files: {}, createdAt: Date.now() };
    await localforage.setItem('users', [...users, newUser]);
    setCurrentUser(newUser);
    return true;
  };

  return (
    <UserContext.Provider value={{ currentUser, setCurrentUser, signIn, signUp, autoSignOut }}>
      {children}
    </UserContext.Provider>
  );
}

  useEffect(() => {
    if (isLoaded) {
      localforage.setItem(CURRENT_USER_KEY, currentUserId).catch(() => {})
    }
  }, [currentUserId, isLoaded])

  const createUser = async (name, password) => {
    if (!name) throw new Error('Name required')
    const exists = users.find(u => u.name === name)
    if (exists) throw new Error('User already exists')
    const id = (crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now())
    const pwdHash = await hashString(password || '')
    const newUser = {
      id,
      name,
      passwordHash: pwdHash,
      files: [null, null, null],
      createdAt: new Date().toISOString()
    }
    const next = [...users, newUser]
    setUsers(next)
    setCurrentUserId(id)
    return newUser
  }

  const authenticate = async (name, password) => {
    const user = users.find(u => u.name === name)
    if (!user) throw new Error('User not found')
    const pwdHash = await hashString(password || '')
    if (pwdHash !== user.passwordHash) throw new Error('Invalid credentials')
    setCurrentUserId(user.id)
    return user
  }

  const signout = async () => {
    setCurrentUserId(null)
  }

  const getCurrentUser = () => users.find(u => u.id === currentUserId) || null

  const setUserFile = (index, fileMeta) => {
    const user = users.find(u => u.id === currentUserId)
    if (!user) throw new Error('No user signed in')
    const next = users.map(u => {
      if (u.id !== currentUserId) return u
      const files = [...(u.files || [null, null, null])]
      files[index] = fileMeta
      return { ...u, files }
    })
    setUsers(next)
  }

  return (
    <UserContext.Provider value={{
      users,
      createUser,
      authenticate,
      signout,
      currentUserId,
      setCurrentUserId,
      getCurrentUser,
      setUserFile,
      isLoaded
    }}>
      {children}
    </UserContext.Provider>
  )
}

export default UserContextWrapper

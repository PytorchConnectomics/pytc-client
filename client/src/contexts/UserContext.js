import React, { createContext, useState, useEffect } from 'react'
import localforage from 'localforage'

export const UserContext = createContext(null)

const USERS_KEY = 'pytc_users'
const CURRENT_USER_KEY = 'pytc_current_user'

async function hashString (str) {
  if (!str) return ''
  const enc = new TextEncoder()
  const data = enc.encode(str)
  const hash = await crypto.subtle.digest('SHA-256', data)
  const hashArray = Array.from(new Uint8Array(hash))
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
}

export const UserContextWrapper = ({ children }) => {
  const [users, setUsers] = useState([])
  const [currentUserId, setCurrentUserId] = useState(null)
  const [isLoaded, setIsLoaded] = useState(false)

  useEffect(() => {
    let mounted = true
    const load = async () => {
      await localforage.removeItem(CURRENT_USER_KEY) // Always sign out on app start
      const stored = await localforage.getItem(USERS_KEY)
      setUsers(stored || [])
      setCurrentUserId(null)
      setIsLoaded(true)
    }
    load()
    return () => { mounted = false }
  }, [])

  useEffect(() => {
    if (isLoaded) {
      localforage.setItem(USERS_KEY, users).catch(() => {})
    }
  }, [users, isLoaded])

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

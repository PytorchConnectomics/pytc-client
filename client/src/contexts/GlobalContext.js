import React, { createContext, useState, useEffect, useCallback } from 'react'
import localforage from 'localforage'

export const AppContext = createContext(null)

const FILE_STATE_DEFAULTS = {
  files: [],
  fileList: [],
  imageFileList: [],
  labelFileList: [],
  currentImage: null,
  currentLabel: null,
  inputImage: null,
  inputLabel: null
}

const FILE_CACHE_KEYS = Object.keys(FILE_STATE_DEFAULTS)
const FILE_OBJECT_STATE_KEYS = FILE_CACHE_KEYS.filter((key) => key !== 'fileList')

const sanitizeFileEntry = (file) => {
  if (!file || typeof file !== 'object') return file
  const {
    uid,
    name,
    originalName,
    path,
    folderPath,
    thumbUrl,
    type,
    status,
    percent,
    size,
    response,
    error,
    lastModified,
    lastModifiedDate,
    url
  } = file
  return {
    uid,
    name,
    originalName: originalName || name,
    path,
    folderPath,
    thumbUrl,
    type,
    status,
    percent,
    size,
    response,
    error,
    lastModified,
    lastModifiedDate,
    url
  }
}

const sanitizePersistedState = (key, state) => {
  if (!FILE_OBJECT_STATE_KEYS.includes(key)) {
    return state
  }
  if (Array.isArray(state)) {
    return state.map((entry) => sanitizeFileEntry(entry))
  }
  return sanitizeFileEntry(state)
}

// Solve delete button error issue
function usePersistedState (key, defaultValue) {
  const [state, setState] = useState(defaultValue)
  const [isLoaded, setIsLoaded] = useState(false)

  useEffect(() => {
    // Fetch the stored value asynchronously when the component mounts
    localforage.getItem(key).then((storedValue) => {
      if (storedValue !== null) {
        setState(storedValue)
      }
      setIsLoaded(true)
    }).catch((err) => {
      console.error('Error retrieving value from localforage:', err)
      setIsLoaded(true)
    })
  }, [key])

  useEffect(() => {
    if (isLoaded) {
      // Save the state to localforage asynchronously whenever it changes
      const valueToPersist = sanitizePersistedState(key, state)
      localforage.setItem(key, valueToPersist).catch((err) => {
        console.error('Error setting value to localforage:', err)
      })
    }
  }, [key, state, isLoaded])

  return [state, setState]
}

// function safeParseJSON(jsonString, defaultValue) {
//   try {
//     return JSON.parse(jsonString) || defaultValue;
//   } catch (e) {
//     console.error("Error parsing JSON:", e);
//     return defaultValue;
//   }
// }

export const ContextWrapper = (props) => {
  const [files, setFiles] = usePersistedState('files', [])
  const [fileList, setFileList] = usePersistedState('fileList', [])
  const [trainingConfig, setTrainingConfig] = usePersistedState('trainingConfig', null)
  const [inferenceConfig, setInferenceConfig] = usePersistedState('inferenceConfig', null)
  const [uploadedYamlFile, setUploadedYamlFile] = usePersistedState('uploadedYamlFile', '')
  const [imageFileList, setImageFileList] = usePersistedState('imageFileList', [])
  const [labelFileList, setLabelFileList] = usePersistedState('labelFileList', [])
  const [outputPath, setOutputPath] = usePersistedState('outputPath', null)
  const [logPath, setLogPath] = usePersistedState('logPath', null)
  const [checkpointPath, setCheckpointPath] = usePersistedState('checkpointPath', null)
  const [currentImage, setCurrentImage] = usePersistedState('currentImage', null)
  const [currentLabel, setCurrentLabel] = usePersistedState('currentLabel', null)
  const [inputImage, setInputImage] = usePersistedState('inputImage', null)
  const [inputLabel, setInputLabel] = usePersistedState('inputLabel', null)
  const [viewer, setViewer] = usePersistedState('viewer', null)
  const [tensorBoardURL, setTensorBoardURL] = usePersistedState('tensorBoardURL', null)

  const resetFileState = useCallback(async () => {
    try {
      await Promise.all(
        FILE_CACHE_KEYS.map((key) => localforage.removeItem(key))
      )
    } catch (error) {
      console.error('Error clearing file cache from storage:', error)
    } finally {
      setFiles(FILE_STATE_DEFAULTS.files)
      setFileList(FILE_STATE_DEFAULTS.fileList)
      setImageFileList(FILE_STATE_DEFAULTS.imageFileList)
      setLabelFileList(FILE_STATE_DEFAULTS.labelFileList)
      setCurrentImage(FILE_STATE_DEFAULTS.currentImage)
      setCurrentLabel(FILE_STATE_DEFAULTS.currentLabel)
      setInputImage(FILE_STATE_DEFAULTS.inputImage)
      setInputLabel(FILE_STATE_DEFAULTS.inputLabel)
    }
  }, [
    setFiles,
    setFileList,
    setImageFileList,
    setLabelFileList,
    setCurrentImage,
    setCurrentLabel,
    setInputImage,
    setInputLabel
  ])

  return (
    <AppContext.Provider
      value={{
        files,
        setFiles,
        fileList,
        setFileList,
        currentImage,
        setCurrentImage,
        currentLabel,
        setCurrentLabel,
        inputImage,
        setInputImage,
        inputLabel,
        setInputLabel,
        viewer,
        setViewer,
        trainingConfig,
        setTrainingConfig,
        imageFileList,
        setImageFileList,
        labelFileList,
        setLabelFileList,
        inferenceConfig,
        setInferenceConfig,
        uploadedYamlFile,
        setUploadedYamlFile,
        outputPath,
        setOutputPath,
        logPath,
        setLogPath,
        checkpointPath,
        setCheckpointPath,
        tensorBoardURL,
        setTensorBoardURL,
        resetFileState
      }}
    >
      {props.children}
    </AppContext.Provider>
  )
}

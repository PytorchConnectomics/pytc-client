import React, { createContext, useState, useEffect, useCallback } from 'react'
import localforage from 'localforage'
import { DEMO_IMAGE_PREVIEW, DEMO_LABEL_PREVIEW } from '../utils/demo_images'

export const AppContext = createContext(null)

const DEMO_DEFAULTS = {
  imagePath: '/Users/adamg/seg.bio/pytc-client/lucchi_test/lucchiIm.tif',
  labelPath: '/Users/adamg/seg.bio/pytc-client/lucchi_test/lucchiLabels.tif',
  checkpointPath: '/Users/adamg/seg.bio/pytc-client/lucchi_test/epoch=269-step=5400.ckpt',
  outputPath: '/Users/adamg/seg.bio/pytc-client/test_output/inference',
  inferenceConfig: `# Lucchi++ Mitochondria Segmentation
experiment_name: lucchi++
description: Mitochondria segmentation on Lucchi++ EM dataset

# System
system:
  training:
    num_gpus: 4
    num_cpus: 8
    num_workers: 8
    batch_size: 16
  inference:
    num_gpus: 1
    num_cpus: 1
    num_workers: 1
    batch_size: 1
  seed: 42

# Model Configuration
model:
  architecture: monai_unet
  input_size: [112, 112, 112]
  output_size: [112, 112, 112]
  in_channels: 1
  out_channels: 1
  filters: [32, 64, 128, 256]
  dropout: 0.1
  loss_functions: [WeightedBCE, DiceLoss]
  loss_weights: [1.0, 1.0]
  loss_kwargs:
    - {reduction: mean}
    - {sigmoid: true, smooth_nr: 1e-5, smooth_dr: 1e-5}

# Data
data:
  train_image: datasets/lucchi++/train_im.h5
  train_label: datasets/lucchi++/train_mito.h5
  train_resolution: [5, 5, 5]
  use_preloaded_cache: true
  patch_size: [112, 112, 112]
  pad_size: [0, 0, 0]
  iter_num_per_epoch: 1280
  image_transform:
    normalize: "0-1"
    clip_percentile_low: 0.0
    clip_percentile_high: 1.0
  augmentation:
    flip: {enabled: true, prob: 0.5, spatial_axis: [0, 1, 2]}
    rotate: {enabled: true, prob: 0.5}
    intensity: {enabled: true, gaussian_noise_prob: 0.2, gaussian_noise_std: 0.03, shift_intensity_prob: 0.4, shift_intensity_offset: 0.1, contrast_prob: 0.4, contrast_range: [0.8, 1.2]}
    misalignment: {enabled: true, prob: 0.4, displacement: 8, rotate_ratio: 0.3}
    missing_section: {enabled: true, prob: 0.3, num_sections: 2}
    motion_blur: {enabled: true, prob: 0.3, sections: 2, kernel_size: 9}

# Optimization
optimization:
  max_epochs: 1000
  gradient_clip_val: 0.5
  accumulate_grad_batches: 1
  precision: "bf16-mixed"
  optimizer:
    name: Adam
    lr: 0.001
    weight_decay: 0.0
    betas: [0.9, 0.999]
    eps: 1.0e-8
  scheduler:
    name: ReduceLROnPlateau
    mode: min
    factor: 0.5
    patience: 50
    threshold: 1.0e-4
    min_lr: 1.0e-6

monitor:
  detect_anomaly: false
  logging:
    scalar: {loss: [train_loss_total_epoch], loss_every_n_steps: 10, val_check_interval: 1.0, benchmark: true}
    images: {enabled: true, max_images: 8, num_slices: 2, log_every_n_epochs: 1, channel_mode: argmax, selected_channels: null}
  checkpoint:
    mode: min
    save_top_k: 1
    save_last: true
    save_every_n_epochs: 10
    use_timestamp: true
  early_stopping:
    enabled: true
    monitor: train_loss_total_epoch
    patience: 100
    mode: min
    min_delta: 1.0e-4
    check_finite: true
    threshold: 0.02
    divergence_threshold: 2.0

# Inference
inference:
  data:
    test_image: /Users/adamg/seg.bio/pytc-client/lucchi_test/lucchiIm.tif
    test_label: /Users/adamg/seg.bio/pytc-client/lucchi_test/lucchiLabels.tif
    test_resolution: [5, 5, 5]
  sliding_window:
    window_size: [112, 112, 112]
    sw_batch_size: 1
    overlap: 0.25
    blending: gaussian
    sigma_scale: 0.25
    padding_mode: replicate
  test_time_augmentation:
    enabled: true
    flip_axes: all
    channel_activations: [[0, 1, 'sigmoid']]
    select_channel: null
    ensemble_mode: mean
  postprocessing:
    output_scale: 255
    output_dtype: uint8
  evaluation:
    enabled: true
    metrics: [jaccard]
`
}

const createMockFile = (path, name, type = 'application/x-hdf', thumbUrl = null) => ({
  uid: 'demo-' + name,
  name: name,
  originalName: name,
  path: path,
  folderPath: path.substring(0, path.lastIndexOf('/')),
  type: type,
  size: 0, // Mock size
  status: 'done',
  thumbUrl: thumbUrl
})

const demoImage = createMockFile(DEMO_DEFAULTS.imagePath, 'lucchiIm.tif', 'image/tiff', DEMO_IMAGE_PREVIEW)
const demoLabel = createMockFile(DEMO_DEFAULTS.labelPath, 'lucchiLabels.tif', 'image/tiff', DEMO_LABEL_PREVIEW)

const FILE_STATE_DEFAULTS = {
  files: [demoImage, demoLabel],
  fileList: [],
  imageFileList: [demoImage],
  labelFileList: [demoLabel],
  currentImage: demoImage,
  currentLabel: demoLabel,
  inputImage: demoImage,
  inputLabel: demoLabel,
  checkpointPath: DEMO_DEFAULTS.checkpointPath,
  outputPath: DEMO_DEFAULTS.outputPath,
  inferenceConfig: DEMO_DEFAULTS.inferenceConfig,
  uploadedYamlFile: { name: 'demo_config.yaml' }
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
function usePersistedState(key, defaultValue) {
  const [state, setState] = useState(defaultValue)
  const [isLoaded, setIsLoaded] = useState(false)

  useEffect(() => {
    // DEMO MODE: Disable loading from storage to force hardcoded defaults
    // localforage.getItem(key).then((storedValue) => {
    //   if (storedValue !== null) {
    //     setState(storedValue)
    //   }
    //   setIsLoaded(true)
    // }).catch((err) => {
    //   console.error('Error retrieving value from localforage:', err)
    //   setIsLoaded(true)
    // })
    setIsLoaded(true)
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
  const [files, setFiles] = usePersistedState('files', FILE_STATE_DEFAULTS.files)
  const [fileList, setFileList] = usePersistedState('fileList', FILE_STATE_DEFAULTS.fileList)
  const [trainingConfig, setTrainingConfig] = usePersistedState('trainingConfig', FILE_STATE_DEFAULTS.trainingConfig)
  const [inferenceConfig, setInferenceConfig] = usePersistedState('inferenceConfig', FILE_STATE_DEFAULTS.inferenceConfig)
  const [uploadedYamlFile, setUploadedYamlFile] = usePersistedState('uploadedYamlFile', FILE_STATE_DEFAULTS.uploadedYamlFile)
  const [imageFileList, setImageFileList] = usePersistedState('imageFileList', FILE_STATE_DEFAULTS.imageFileList)
  const [labelFileList, setLabelFileList] = usePersistedState('labelFileList', FILE_STATE_DEFAULTS.labelFileList)
  const [outputPath, setOutputPath] = usePersistedState('outputPath', FILE_STATE_DEFAULTS.outputPath)
  const [logPath, setLogPath] = usePersistedState('logPath', FILE_STATE_DEFAULTS.logPath)
  const [checkpointPath, setCheckpointPath] = usePersistedState('checkpointPath', FILE_STATE_DEFAULTS.checkpointPath)
  const [currentImage, setCurrentImage] = usePersistedState('currentImage', FILE_STATE_DEFAULTS.currentImage)
  const [currentLabel, setCurrentLabel] = usePersistedState('currentLabel', FILE_STATE_DEFAULTS.currentLabel)
  const [inputImage, setInputImage] = usePersistedState('inputImage', FILE_STATE_DEFAULTS.inputImage)
  const [inputLabel, setInputLabel] = usePersistedState('inputLabel', FILE_STATE_DEFAULTS.inputLabel)
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

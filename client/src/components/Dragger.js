//  global FileReader
import React, { useContext, useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { Button, Input, message, Modal, Space, Upload } from 'antd'
import { InboxOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons'
import { AppContext } from '../contexts/GlobalContext'
import { DEFAULT_IMAGE } from '../utils/utils'
import UTIF from 'utif'

const path = require('path')

const ensureTrailingSeparator = (dirPath) => {
  if (!dirPath) return ''
  return dirPath.endsWith(path.sep) ? dirPath : dirPath + path.sep
}

const getFolderPath = (uploadFile, originPath) => {
  if (uploadFile?.folderPath) {
    return ensureTrailingSeparator(uploadFile.folderPath)
  }
  if (!originPath) return ''
  return ensureTrailingSeparator(path.dirname(originPath))
}

const enrichFileMetadata = (uploadFile) => {
  const originPath =
    uploadFile?.originFileObj?.path ||
    uploadFile?.path
  const folderPath = getFolderPath(uploadFile, originPath)

  const enhancedFile = { ...uploadFile }
  if (originPath) {
    enhancedFile.path = originPath
  }
  if (folderPath) {
    enhancedFile.folderPath = folderPath
  }
  if (!enhancedFile.originalName) {
    const derivedOriginalName =
      uploadFile?.originFileObj?.name ||
      uploadFile?.name ||
      enhancedFile.name
    if (derivedOriginalName) {
      enhancedFile.originalName = derivedOriginalName
    }
  }
  return enhancedFile
}

export function Dragger() {
  const context = useContext(AppContext)
  const {
    setFiles,
    files,
    setFileList,
    setImageFileList,
    setLabelFileList,
    resetFileState
  } = context
  const objectUrlMapRef = useRef(new Map())

  const revokeObjectUrl = useCallback((uid) => {
    const url = objectUrlMapRef.current.get(uid)
    if (url) {
      URL.revokeObjectURL(url)
      objectUrlMapRef.current.delete(uid)
    }
  }, [])

  const revokeAllObjectUrls = useCallback(() => {
    objectUrlMapRef.current.forEach((url) => URL.revokeObjectURL(url))
    objectUrlMapRef.current.clear()
  }, [])

  const filesByUid = useMemo(() => {
    const map = new Map()
    if (Array.isArray(files)) {
      files.forEach((file) => {
        map.set(file.uid, file)
      })
    }
    return map
  }, [files])

  // const getBase64 = (file) =>
  //   new Promise((resolve, reject) => {
  //     const reader = new FileReader()
  //     reader.readAsDataURL(file)
  //     reader.onload = () => resolve(reader.result)
  //     reader.onerror = (error) => reject(error)
  //   })

  const onChange = (info) => {
    const { status } = info.file
    if (status === 'done') {
      const originPath =
        info.file?.originFileObj?.path ||
        info.file?.path
      console.log('file found at:', originPath)

      message.success(`${info.file.name} file uploaded successfully.`)
      const updatedFiles = info.fileList.map(enrichFileMetadata)
      setFiles(updatedFiles)
      console.log('done')
    } else if (status === 'error') {
      console.log('error')
      message.error(`${info.file.name} file upload failed.`)
      revokeObjectUrl(info.file.uid)
    } else if (status === 'removed') {
      console.log(info.fileList)
      setFiles(info.fileList.map(enrichFileMetadata))
      revokeObjectUrl(info.file.uid)
    }
  }

  const uploadImage = async (options) => {
    const { onSuccess, onError } = options
    try {
      onSuccess('Ok')
    } catch (err) {
      onError({ err })
    }
  }

  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewImage, setPreviewImage] = useState('')
  const [previewTitle, setPreviewTitle] = useState('')
  const [value, setValue] = useState('')
  const [fileUID, setFileUID] = useState(null)
  const [previewFileFolderPath, setPreviewFileFolderPath] = useState('')
  const [fileType, setFileType] = useState('Image')

  useEffect(() => {
    if (!files || files.length === 0) return
    const needsFolderPath = files.some(
      (file) =>
        !file.folderPath &&
        (file?.originFileObj?.path || file?.path)
    )
    if (needsFolderPath) {
      setFiles(
        files.map((file) =>
          !file.folderPath ? enrichFileMetadata(file) : file
        )
      )
    }
  }, [files, setFiles])

  const handleText = (event) => {
    setValue(event.target.value)
  }

  const handleDropdownChange = (event) => {
    setFileType(event.target.value)
  }

  const fetchFile = async (file) => {
    try {
      if (fileType === 'Label') {
        setLabelFileList((prevLabelList) => [...prevLabelList, file])
      } else if (fileType === 'Image') {
        setImageFileList((prevImageList) => [...prevImageList, file])
      }
    } catch (error) {
      console.error(error)
    }
  }

  const handleSubmit = () => {
    if (!fileUID) return
    const targetFile = filesByUid.get(fileUID)
    if (!targetFile) return

    const updates = {}
    if (previewFileFolderPath !== '') {
      updates.folderPath = previewFileFolderPath
      setPreviewFileFolderPath('')
    }
    if (value !== '') {
      updates.name = value
      setValue('')
    }

    const updatedFile = Object.keys(updates).length > 0
      ? { ...targetFile, ...updates }
      : targetFile

    if (Object.keys(updates).length > 0) {
      setFiles((prevFiles) =>
        prevFiles.map((file) =>
          file.uid === fileUID ? { ...file, ...updates } : file
        )
      )

      if (updates.name) {
        setFileList((prevList) =>
          prevList.map((entry) =>
            entry.value === fileUID ? { ...entry, label: updates.name } : entry
          )
        )
      }
    }

    fetchFile(updatedFile)
    setPreviewOpen(false)
  }

  const handleClearCache = async () => {
    try {
      revokeAllObjectUrls()
      await resetFileState()
      message.success('File cache cleared successfully.')
    } catch (error) {
      console.error('Failed to clear file cache:', error)
      message.error('Failed to clear file cache.')
    }
  }

  const handleRevert = () => {
    if (!fileUID) {
      setPreviewOpen(false)
      return
    }
    const targetFile = filesByUid.get(fileUID)
    const oldName = targetFile?.originFileObj?.name || targetFile?.originalName
    if (!oldName) {
      setPreviewOpen(false)
      return
    }
    setFiles((prevFiles) =>
      prevFiles.map((file) =>
        file.uid === fileUID ? { ...file, name: oldName } : file
      )
    )
    setFileList((prevList) =>
      prevList.map((entry) =>
        entry.value === fileUID ? { ...entry, label: oldName } : entry
      )
    )
    setPreviewOpen(false)
  }

  const handleCancel = () => setPreviewOpen(false)
  // Function to generate preview for TIFF files
  const generateTiffPreview = (file, callback) => {
    const reader = new FileReader()
    reader.onload = function (event) {
      try {
        const buffer = new Uint8Array(event.target.result)
        console.log('Buffer length: ', buffer.length) // Log buffer length in bytes
        const tiffPages = UTIF.decode(buffer)
        // Check if tiffPages array is not empty
        if (tiffPages.length === 0) throw new Error('No TIFF pages found')
        const firstPage = tiffPages[0]
        console.log('First page before decoding:', firstPage) // Log first page object before decoding
        // Ensure the firstPage has necessary tags before decoding
        if (!firstPage.t256 || !firstPage.t257) throw new Error('First page is missing essential tags (width and height)')
        UTIF.decodeImage(buffer, firstPage) // firstPage before and after decoding, the result is same.
        console.log('TIFF first page after decoding: ', firstPage) // Log the first page object
        // Extract width and height from the TIFF tags
        const width = firstPage.t256 ? firstPage.t256[0] : 0
        const height = firstPage.t257 ? firstPage.t257[0] : 0
        // Check if width and height are valid
        if (width > 0 && height > 0) {
          const rgba = UTIF.toRGBA8(firstPage) // Uint8Array with RGBA pixels
          // Create a canvas to draw the TIFF image
          const canvas = document.createElement('canvas')
          const ctx = canvas.getContext('2d')
          canvas.width = width
          canvas.height = height
          const imageData = ctx.createImageData(width, height)
          imageData.data.set(rgba)
          ctx.putImageData(imageData, 0, 0)
          const dataURL = canvas.toDataURL()
          console.log('Canvas data URL:', dataURL)
          callback(dataURL)
        } else {
          console.error('TIFF image has invalid dimensions:', { width, height })
          message.error('TIFF image has invalid dimensions.')
          setPreviewImage(DEFAULT_IMAGE) // Fallback to default image
        }
      } catch (error) {
        console.error('Failed to generate TIFF preview:', error)
        message.error('Failed to generate TIFF preview.')
        setPreviewImage(DEFAULT_IMAGE) // Fallback to default image
      }
    }
    reader.readAsArrayBuffer(file)
  }

  // When click preview eye icon, implement handlePreview function
  const handlePreview = async (file) => {
    setFileUID(file.uid)
    setPreviewOpen(true)
    setPreviewImage(file.thumbUrl)
    setPreviewTitle(file.name || file.url.substring(file.url.lastIndexOf('/') + 1))
    const targetFile = filesByUid.get(file.uid)
    if (targetFile?.folderPath) {
      setPreviewFileFolderPath(targetFile.folderPath)
    } else {
      const originPath =
        file?.originFileObj?.path ||
        file?.path
      setPreviewFileFolderPath(
        originPath ? ensureTrailingSeparator(path.dirname(originPath)) : ''
      )
    }
  }

  const listItemStyle = {
    display: 'inline-block',
    width: '185px',
    height: 'auto',
    verticalAlign: 'top'
  }

  // when click or drag file to this area to upload, below function will be deployed.
  const handleBeforeUpload = (file) => {
    // Create a URL for the thumbnail using object URL
    if (file.type === 'image/tiff' || file.type === 'image/tif') {
      return new Promise((resolve) => {
        generateTiffPreview(file, (dataURL) => {
          file.thumbUrl = dataURL
          console.log('file thumbUrl inside callback is', file.thumbUrl)
          resolve(file)
        })
        console.log('file thumbUrl is', file.thumbUrl)
      })
    } else {
      file.thumbUrl = URL.createObjectURL(file)
      objectUrlMapRef.current.set(file.uid, file.thumbUrl)
    }
    return true // Allow the upload
  }

  useEffect(() => {
    return () => {
      revokeAllObjectUrls()
    }
  }, [revokeAllObjectUrls])

  const handleRemove = (file) => {
    const newFiles = files.filter((f) => f.uid !== file.uid)
    setFiles(newFiles)
    revokeObjectUrl(file.uid)
  }

  return (
    <>
      <Upload.Dragger
        multiple
        onChange={onChange}
        customRequest={uploadImage}
        beforeUpload={handleBeforeUpload}
        showUploadList={false}
        style={{ padding: '20px 0' }}
      >
        <p className='ant-upload-drag-icon'>
          <InboxOutlined />
        </p>
        <p className='ant-upload-text'>
          Click or drag file to this area to upload
        </p>
      </Upload.Dragger>

      <div style={{
        marginTop: '16px',
        maxHeight: '30vh',
        overflowY: 'auto',
        overflowX: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px'
      }}>
        {files && files.map((file) => (
          <div
            key={file.uid}
            style={{
              display: 'flex',
              alignItems: 'center',
              border: '1px solid #d9d9d9',
              borderRadius: '4px',
              padding: '4px',
              backgroundColor: '#fafafa',
              width: '100%',
              boxSizing: 'border-box'
            }}
          >
            <div style={{
              width: '32px',
              height: '32px',
              marginRight: '8px',
              flexShrink: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              overflow: 'hidden',
              border: '1px solid #f0f0f0',
              borderRadius: '2px',
              backgroundColor: '#fff'
            }}>
              {file.thumbUrl ? (
                <img
                  src={file.thumbUrl}
                  alt={file.name}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              ) : (
                <InboxOutlined style={{ fontSize: '16px', color: '#ccc' }} />
              )}
            </div>

            <div style={{ flex: 1, minWidth: 0, marginRight: '4px' }}>
              <div style={{
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                fontWeight: 500,
                fontSize: '12px'
              }}>
                {file.name}
              </div>
            </div>

            <Space size={0}>
              <Button
                type="text"
                icon={<EyeOutlined />}
                onClick={() => handlePreview(file)}
                size="small"
                style={{ padding: '0 4px' }}
              />
              <Button
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={() => handleRemove(file)}
                size="small"
                style={{ padding: '0 4px' }}
              />
            </Space>
          </div>
        ))}
      </div>

      <Button type='default' style={{ width: '100%', marginTop: '16px' }} onClick={handleClearCache}>
        Clear File Cache
      </Button>
      <Modal
        open={previewOpen}
        title={previewTitle}
        footer={null}
        onCancel={handleCancel}
      >
        <Space direction='vertical' style={{ width: '100%' }}>
          <Space.Compact block>

            <select onChange={handleDropdownChange} style={{ flex: 1 }}>
              <option value='' disabled selected>Please select input filetype</option>
              <option value='Image'>Image</option>
              <option value='Label'>Label</option>
            </select>
            <Button onClick={() => handleSubmit()}>Submit</Button>
            <Button onClick={handleRevert}>Revert</Button>
          </Space.Compact>
          <Space.Compact block>
            <Input
              value={value}
              placeholder='Alternative file name'
              onChange={handleText}
            />
          </Space.Compact>
          <img
            alt='example'
            style={{
              width: '100%'
            }}
            src={previewImage}
          />
        </Space>
      </Modal>
    </>
  )
}

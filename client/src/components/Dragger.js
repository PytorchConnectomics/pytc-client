//  global FileReader
import React, { useContext, useState } from 'react'
import { Button, Input, message, Modal, Space, Upload } from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import { AppContext } from '../contexts/GlobalContext'
import { DEFAULT_IMAGE } from '../utils/utils'
import UTIF from 'utif'

const path = require('path')

export function Dragger () {
  const context = useContext(AppContext)

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
      console.log('file found at:', info.file.originFileObj.path)

      message.success(`${info.file.name} file uploaded successfully.`)
      if (window.require) {
        const modifiedFile = { ...info.file, path: info.file.originFileObj.path }
        context.setFiles([...context.files, modifiedFile])
      } else {
        context.setFiles([...info.fileList])
      }
      console.log('done')
    } else if (status === 'error') {
      console.log('error')
      message.error(`${info.file.name} file upload failed.`)
    } else if (status === 'removed') {
      console.log(info.fileList)
      context.setFiles([...info.fileList])
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

  const handleText = (event) => {
    setValue(event.target.value)
  }

  const handleDropdownChange = (event) => {
    setFileType(event.target.value)
  }

  const fetchFile = async (file) => {
    try {
      if (fileType === 'Label') {
        context.setLabelFileList((prevLabelList) => [...prevLabelList, file])
      } else if (fileType === 'Image') {
        context.setImageFileList((prevImageList) => [...prevImageList, file])
      }
    } catch (error) {
      console.error(error)
    }
  }

  const handleSubmit = (type) => {
    console.log('submitting path', previewFileFolderPath)
    if (previewFileFolderPath !== '') {
      context.files.find(
        (targetFile) => targetFile.uid === fileUID
      ).folderPath = previewFileFolderPath
      setPreviewFileFolderPath('')
    }
    if (value !== '') {
      context.files.find((targetFile) => targetFile.uid === fileUID).name =
        value
      context.fileList.find(
        (targetFile) => targetFile.value === fileUID
      ).label = value
      setValue('')
    }
    fetchFile(context.files.find((targetFile) => targetFile.uid === fileUID))
    setPreviewOpen(false)
  }

  const handleClearCache = async () => {
    context.setFileList([])
    context.setImageFileList([])
    context.setLabelFileList([])
    message.success('File list cleared successfully.')
  }

  const handleRevert = () => {
    const oldName = context.files.find((targetFile) => targetFile.uid === fileUID)
      .originFileObj.name
    context.files.find((targetFile) => targetFile.uid === fileUID).name =
      oldName
    context.fileList.find((targetFile) => targetFile.value === fileUID).label =
      oldName
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
        console.log('First page before decoding:', firstPage) // Log first page object before decodin

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
    if (
      context.files.find(targetFile => targetFile.uid === file.uid) &&
      context.files.find(targetFile => targetFile.uid === file.uid).folderPath) {
      setPreviewFileFolderPath(
        context.files.find(targetFile => targetFile.uid === file.uid)
          .folderPath
      )
    } else {
      // Directory name with trailing slash
      setPreviewFileFolderPath(path.dirname(file.originFileObj.path) + '/')
    }
  }

  const listItemStyle = {
    width: '185px'
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
    }
    return true // Allow the upload
  }

  return (
    <>
      <Upload.Dragger
        multiple
        onChange={onChange}
        customRequest={uploadImage}
        beforeUpload={handleBeforeUpload}
        onPreview={handlePreview}
        listType='picture-card'
        style={{ maxHeight: '20vh', maxWidth: '10vw%' }}
        itemRender={(originNode, file) => (
          <div style={listItemStyle}>{originNode}</div>
        )}
      >
        <p className='ant-upload-drag-icon'>
          <InboxOutlined />
        </p>
        <p className='ant-upload-text'>
          Click or drag file to this area to upload
        </p>
      </Upload.Dragger>
      <Button type='default' onClick={handleClearCache}>
        Clear File Cache
      </Button>
      <Modal
        open={previewOpen}
        title={previewTitle}
        footer={null}
        onCancel={handleCancel}
      >
        <Space direction='vertical'>
          <Space.Compact block>

            <select onChange={handleDropdownChange}>
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

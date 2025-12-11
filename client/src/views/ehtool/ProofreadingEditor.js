import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Card, Button, Slider, InputNumber, Space, message, Tooltip } from 'antd';
import {
  BgColorsOutlined,
  ClearOutlined,
  UndoOutlined,
  RedoOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  SaveOutlined,
  LeftOutlined,
  RightOutlined,
  ZoomInOutlined,
  ZoomOutOutlined
} from '@ant-design/icons';

/**
 * Proofreading Editor Component
 * Canvas-based image editor with paint/erase brush tools for mask correction
 */
function ProofreadingEditor({
  imageBase64,
  maskBase64,
  onSave,
  onNext,
  onPrevious,
  currentLayer,
  totalLayers,
  layerName
}) {
  const canvasRef = useRef(null);
  const [tool, setTool] = useState('paint'); // 'paint' or 'erase'
  const [paintBrushSize, setPaintBrushSize] = useState(10);
  const [eraseBrushSize, setEraseBrushSize] = useState(10);
  const [showMask, setShowMask] = useState(true);
  const [zoom, setZoom] = useState(1.0);
  const [isDrawing, setIsDrawing] = useState(false);
  const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 });

  // Image and mask data
  const imageDataRef = useRef(null);
  const maskDataRef = useRef(null);
  const originalMaskRef = useRef(null);

  // Undo/Redo stacks
  const [undoStack, setUndoStack] = useState([]);
  const [redoStack, setRedoStack] = useState([]);

  // Canvas offset for panning
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });

  // Load images when props change
  useEffect(() => {
    if (imageBase64 && canvasRef.current) {
      loadImages();
    }
  }, [imageBase64, maskBase64]);

  // Redraw canvas when zoom, offset, or visibility changes
  useEffect(() => {
    if (canvasRef.current && imageDataRef.current) {
      drawCanvas();
    }
  }, [zoom, offset, showMask]);

  const loadImages = async () => {
    const canvas = canvasRef.current;
    if (!canvas) {
      console.error('Canvas ref is null');
      return;
    }

    console.log('Loading images:', { imageBase64: !!imageBase64, maskBase64: !!maskBase64 });

    const ctx = canvas.getContext('2d');

    try {
      // Load image
      const img = new Image();

      // DIAGNOSTIC: Check if base64 is valid
      if (!imageBase64) {
        console.error('Image base64 is null or empty');
        throw new Error('Image data is missing');
      }
      console.log('Setting image src, length:', imageBase64.length);

      // Check if base64 string already has the prefix
      if (imageBase64.startsWith('data:image')) {
        img.src = imageBase64;
      } else {
        img.src = `data:image/png;base64,${imageBase64}`;
      }

      await new Promise((resolve, reject) => {
        img.onload = () => {
          console.log('Image loaded successfully:', img.width, 'x', img.height);
          // Set canvas size to image size
          canvas.width = img.width;
          canvas.height = img.height;

          // Draw image to get pixel data
          ctx.drawImage(img, 0, 0);
          imageDataRef.current = ctx.getImageData(0, 0, canvas.width, canvas.height);
          console.log('Image data captured');

          resolve();
        };
        img.onerror = (e) => {
          console.error('Failed to load image object:', e);
          // Try to log more details about the error
          console.log('Image src start:', img.src.substring(0, 50));
          reject(new Error('Failed to load image object'));
        };
      });

      // Load or create mask
      if (maskBase64) {
        const maskImg = new Image();

        // Check if base64 string already has the prefix
        if (maskBase64.startsWith('data:image')) {
          maskImg.src = maskBase64;
        } else {
          maskImg.src = `data:image/png;base64,${maskBase64}`;
        }

        await new Promise((resolve, reject) => {
          maskImg.onload = () => {
            console.log('Mask loaded:', maskImg.width, 'x', maskImg.height);
            // Create temporary canvas for mask
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = canvas.width;
            tempCanvas.height = canvas.height;
            const tempCtx = tempCanvas.getContext('2d');

            tempCtx.drawImage(maskImg, 0, 0);
            maskDataRef.current = tempCtx.getImageData(0, 0, canvas.width, canvas.height);
            originalMaskRef.current = new ImageData(
              new Uint8ClampedArray(maskDataRef.current.data),
              canvas.width,
              canvas.height
            );
            console.log('Mask data captured');

            resolve();
          };
          maskImg.onerror = (e) => {
            console.error('Failed to load mask:', e);
            reject(e);
          };
        });
      } else {
        console.log('No mask provided, creating empty mask');
        // Create empty mask
        maskDataRef.current = new ImageData(canvas.width, canvas.height);
        originalMaskRef.current = new ImageData(canvas.width, canvas.height);
      }

      // Reset undo/redo
      setUndoStack([]);
      setRedoStack([]);

      // Reset zoom and offset
      setZoom(1.0);
      setOffset({ x: 0, y: 0 });

      console.log('Drawing canvas');
      drawCanvas();
    } catch (error) {
      console.error('Error loading images:', error);
      message.error('Failed to load images');
    }
  };

  const drawCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas || !imageDataRef.current) {
      console.log('Cannot draw canvas:', { canvas: !!canvas, imageData: !!imageDataRef.current });
      return;
    }

    const ctx = canvas.getContext('2d');

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw image
    ctx.putImageData(imageDataRef.current, 0, 0);

    // Draw mask overlay if visible
    if (showMask && maskDataRef.current) {
      // Create a temporary canvas for the mask overlay
      const tempCanvas = document.createElement('canvas');
      tempCanvas.width = canvas.width;
      tempCanvas.height = canvas.height;
      const tempCtx = tempCanvas.getContext('2d');

      // Create overlay with transparency
      const overlayData = createMaskOverlay(maskDataRef.current);
      tempCtx.putImageData(overlayData, 0, 0);

      // Composite the overlay onto the main canvas
      ctx.drawImage(tempCanvas, 0, 0);
    }
  };

  const createMaskOverlay = (maskData) => {
    const width = maskData.width;
    const height = maskData.height;
    const overlay = new ImageData(width, height);

    for (let i = 0; i < maskData.data.length; i += 4) {
      const maskValue = maskData.data[i]; // Assuming grayscale mask

      if (maskValue > 0) {
        // White overlay with transparency
        overlay.data[i] = 255;     // R
        overlay.data[i + 1] = 255; // G
        overlay.data[i + 2] = 255; // B
        overlay.data[i + 3] = 180; // A (70% opacity)
      } else {
        // Fully transparent
        overlay.data[i] = 0;
        overlay.data[i + 1] = 0;
        overlay.data[i + 2] = 0;
        overlay.data[i + 3] = 0;
      }
    }

    return overlay;
  };

  const saveToUndoStack = () => {
    if (!maskDataRef.current) return;

    const maskCopy = new ImageData(
      new Uint8ClampedArray(maskDataRef.current.data),
      maskDataRef.current.width,
      maskDataRef.current.height
    );

    setUndoStack(prev => [...prev, maskCopy]);
    setRedoStack([]); // Clear redo stack on new action
  };

  const handleUndo = () => {
    if (undoStack.length === 0) return;

    const previousState = undoStack[undoStack.length - 1];

    // Save current state to redo stack
    const currentCopy = new ImageData(
      new Uint8ClampedArray(maskDataRef.current.data),
      maskDataRef.current.width,
      maskDataRef.current.height
    );
    setRedoStack(prev => [...prev, currentCopy]);

    // Restore previous state
    maskDataRef.current = new ImageData(
      new Uint8ClampedArray(previousState.data),
      previousState.width,
      previousState.height
    );

    setUndoStack(prev => prev.slice(0, -1));
    drawCanvas();
  };

  const handleRedo = () => {
    if (redoStack.length === 0) return;

    const nextState = redoStack[redoStack.length - 1];

    // Save current state to undo stack
    const currentCopy = new ImageData(
      new Uint8ClampedArray(maskDataRef.current.data),
      maskDataRef.current.width,
      maskDataRef.current.height
    );
    setUndoStack(prev => [...prev, currentCopy]);

    // Restore next state
    maskDataRef.current = new ImageData(
      new Uint8ClampedArray(nextState.data),
      nextState.width,
      nextState.height
    );

    setRedoStack(prev => prev.slice(0, -1));
    drawCanvas();
  };

  const getCanvasCoordinates = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    return {
      x: Math.floor((e.clientX - rect.left) * scaleX),
      y: Math.floor((e.clientY - rect.top) * scaleY)
    };
  };

  const drawBrush = (x, y) => {
    if (!maskDataRef.current) return;

    const brushSize = tool === 'paint' ? paintBrushSize : eraseBrushSize;
    const radius = Math.floor(brushSize / 2);
    const value = tool === 'paint' ? 255 : 0;

    const data = maskDataRef.current.data;
    const width = maskDataRef.current.width;

    // Draw circle
    for (let dy = -radius; dy <= radius; dy++) {
      for (let dx = -radius; dx <= radius; dx++) {
        if (dx * dx + dy * dy <= radius * radius) {
          const px = x + dx;
          const py = y + dy;

          if (px >= 0 && px < width && py >= 0 && py < maskDataRef.current.height) {
            const idx = (py * width + px) * 4;
            data[idx] = value;
            data[idx + 1] = value;
            data[idx + 2] = value;
            data[idx + 3] = 255;
          }
        }
      }
    }

    drawCanvas();
  };

  const handleMouseDown = (e) => {
    if (e.button === 1 || (e.button === 0 && e.ctrlKey)) {
      // Middle mouse or Ctrl+Click for panning
      setIsPanning(true);
      setPanStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
      return;
    }

    if (e.button !== 0) return; // Only left click for drawing

    const coords = getCanvasCoordinates(e);
    if (!coords) return;

    saveToUndoStack();
    setIsDrawing(true);
    drawBrush(coords.x, coords.y);
  };

  const handleMouseMove = (e) => {
    const coords = getCanvasCoordinates(e);
    if (coords) {
      setCursorPos(coords);
    }

    if (isPanning) {
      setOffset({
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y
      });
      return;
    }

    if (!isDrawing) return;

    if (coords) {
      drawBrush(coords.x, coords.y);
    }
  };

  const handleMouseUp = () => {
    setIsDrawing(false);
    setIsPanning(false);
  };

  const handleWheel = (e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      setZoom(prev => Math.max(0.1, Math.min(5.0, prev + delta)));
    }
  };

  const handleSave = () => {
    if (!maskDataRef.current) {
      message.error('No mask data to save');
      return;
    }

    // Convert mask ImageData to base64
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = maskDataRef.current.width;
    tempCanvas.height = maskDataRef.current.height;
    const tempCtx = tempCanvas.getContext('2d');
    tempCtx.putImageData(maskDataRef.current, 0, 0);

    const maskBase64 = tempCanvas.toDataURL('image/png').split(',')[1];

    if (onSave) {
      onSave(maskBase64);
    }
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Prevent shortcuts when typing in input fields
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

      switch (e.key.toLowerCase()) {
        case 'p':
          setTool('paint');
          break;
        case 'e':
          setTool('erase');
          break;
        case 'z':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            if (e.shiftKey) {
              handleRedo();
            } else {
              handleUndo();
            }
          }
          break;
        case 'y':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            handleRedo();
          }
          break;
        case 's':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            handleSave();
          }
          break;
        case 'a':
        case 'arrowleft':
          if (onPrevious) onPrevious();
          break;
        case 'd':
        case 'arrowright':
          if (onNext) onNext();
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [undoStack, redoStack, onNext, onPrevious]);

  const brushSize = tool === 'paint' ? paintBrushSize : eraseBrushSize;

  return (
    <div style={{ display: 'flex', height: '100%', gap: '16px' }}>
      {/* Left Panel - Tools */}
      <Card
        title="Tools"
        style={{ width: '280px', height: 'fit-content' }}
        size="small"
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {/* Tool Selection */}
          <div>
            <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>Mode</div>
            <Space>
              <Button
                type={tool === 'paint' ? 'primary' : 'default'}
                icon={<BgColorsOutlined />}
                onClick={() => setTool('paint')}
              >
                Paint (P)
              </Button>
              <Button
                type={tool === 'erase' ? 'primary' : 'default'}
                icon={<ClearOutlined />}
                onClick={() => setTool('erase')}
              >
                Erase (E)
              </Button>
            </Space>
          </div>

          {/* Brush Sizes */}
          <div>
            <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>Paint Brush Size</div>
            <Slider
              min={1}
              max={64}
              value={paintBrushSize}
              onChange={setPaintBrushSize}
            />
            <InputNumber
              min={1}
              max={64}
              value={paintBrushSize}
              onChange={setPaintBrushSize}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>Erase Brush Size</div>
            <Slider
              min={1}
              max={64}
              value={eraseBrushSize}
              onChange={setEraseBrushSize}
            />
            <InputNumber
              min={1}
              max={64}
              value={eraseBrushSize}
              onChange={setEraseBrushSize}
              style={{ width: '100%' }}
            />
          </div>

          {/* Undo/Redo */}
          <div>
            <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>History</div>
            <Space>
              <Tooltip title="Undo (Ctrl+Z)">
                <Button
                  icon={<UndoOutlined />}
                  onClick={handleUndo}
                  disabled={undoStack.length === 0}
                >
                  Undo
                </Button>
              </Tooltip>
              <Tooltip title="Redo (Ctrl+Shift+Z)">
                <Button
                  icon={<RedoOutlined />}
                  onClick={handleRedo}
                  disabled={redoStack.length === 0}
                >
                  Redo
                </Button>
              </Tooltip>
            </Space>
          </div>

          {/* Visibility */}
          <div>
            <Button
              icon={showMask ? <EyeInvisibleOutlined /> : <EyeOutlined />}
              onClick={() => setShowMask(!showMask)}
              block
            >
              {showMask ? 'Hide Mask' : 'Show Mask'}
            </Button>
          </div>

          {/* Zoom */}
          <div>
            <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>Zoom ({Math.round(zoom * 100)}%)</div>
            <Space>
              <Button
                icon={<ZoomOutOutlined />}
                onClick={() => setZoom(prev => Math.max(0.1, prev - 0.1))}
              />
              <Button onClick={() => setZoom(1.0)}>Reset</Button>
              <Button
                icon={<ZoomInOutlined />}
                onClick={() => setZoom(prev => Math.min(5.0, prev + 0.1))}
              />
            </Space>
          </div>

          {/* Save */}
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSave}
            block
            size="large"
          >
            Save (Ctrl+S)
          </Button>
        </Space>
      </Card>

      {/* Center - Canvas */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Layer Navigation */}
        {totalLayers > 1 && (
          <Card size="small">
            <Space style={{ width: '100%', justifyContent: 'space-between' }}>
              <Button
                icon={<LeftOutlined />}
                onClick={onPrevious}
                disabled={currentLayer === 0}
              >
                Previous (A)
              </Button>
              <span style={{ fontWeight: 'bold' }}>
                {layerName || `Layer ${currentLayer + 1}`} / {totalLayers}
              </span>
              <Button
                icon={<RightOutlined />}
                onClick={onNext}
                disabled={currentLayer === totalLayers - 1}
              >
                Next (D)
              </Button>
            </Space>
          </Card>
        )}

        {/* Canvas Container */}
        <Card
          style={{ flex: 1, overflow: 'hidden' }}
          bodyStyle={{
            height: '100%',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            position: 'relative',
            cursor: isPanning ? 'grabbing' : 'none'
          }}
        >
          <div style={{ position: 'relative' }}>
            <canvas
              ref={canvasRef}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
              onWheel={handleWheel}
              style={{
                border: '1px solid #d9d9d9',
                transform: `scale(${zoom}) translate(${offset.x / zoom}px, ${offset.y / zoom}px)`,
                transformOrigin: 'center',
                imageRendering: 'pixelated'
              }}
            />
            {/* Custom Cursor */}
            {!isPanning && (
              <div
                style={{
                  position: 'absolute',
                  left: cursorPos.x * zoom,
                  top: cursorPos.y * zoom,
                  width: brushSize * zoom,
                  height: brushSize * zoom,
                  border: `2px solid ${tool === 'paint' ? '#1890ff' : '#ff4d4f'}`,
                  borderRadius: '50%',
                  pointerEvents: 'none',
                  transform: 'translate(-50%, -50%)',
                  zIndex: 1000
                }}
              />
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

export default ProofreadingEditor;

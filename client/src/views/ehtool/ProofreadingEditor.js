import React, { useState, useRef, useEffect, useCallback, forwardRef, useImperativeHandle } from 'react';
import { Card, Button, Slider, InputNumber, Space, message, Tooltip, Divider } from 'antd';
import {
  EditOutlined,
  ClearOutlined,
  UndoOutlined,
  RedoOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  SaveOutlined,
  LeftOutlined,
  RightOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
  DragOutlined
} from '@ant-design/icons';

/**
 * Proofreading Editor Component
 * Canvas-based image editor with paint/erase brush tools for mask correction
 */
const ProofreadingEditor = forwardRef(({
  imageBase64,
  maskBase64,
  onSave,
  onNext,
  onPrevious,
  currentLayer,
  totalLayers,
  layerName
}, ref) => {
  const canvasRef = useRef(null);
  const minimapRef = useRef(null);
  const containerRef = useRef(null);
  const [tool, setTool] = useState('paint'); // 'paint', 'erase', or 'hand'
  const [paintBrushSize, setPaintBrushSize] = useState(10);
  const [eraseBrushSize, setEraseBrushSize] = useState(10);
  const [showMask, setShowMask] = useState(true);
  const [zoom, setZoom] = useState(1.0);
  const [isDrawing, setIsDrawing] = useState(false);
  const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 }); // Image coordinates
  const [mousePos, setMousePos] = useState(null); // Container/Screen coordinates

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
  const [canvasDimensions, setCanvasDimensions] = useState({ width: 0, height: 0 });

  // Expose handleSave to parent
  useImperativeHandle(ref, () => ({
    save: handleSave
  }));

  // Load images when props change
  useEffect(() => {
    if (imageBase64 && canvasRef.current) {
      loadImages();
    }
  }, [imageBase64, maskBase64]);

  // Redraw canvas when zoom, offset, visibility, or dimensions change
  useEffect(() => {
    if (canvasRef.current && imageDataRef.current) {
      drawCanvas();
      drawMinimap();
    }
  }, [zoom, offset, showMask, canvasDimensions]);

  const loadImages = async () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');

    try {
      const img = new Image();
      if (!imageBase64) throw new Error('Image data is missing');

      if (imageBase64.startsWith('data:image')) {
        img.src = imageBase64;
      } else {
        img.src = `data:image/png;base64,${imageBase64}`;
      }

      await new Promise((resolve, reject) => {
        img.onload = () => {
          canvas.width = img.width;
          canvas.height = img.height;
          ctx.drawImage(img, 0, 0);
          imageDataRef.current = ctx.getImageData(0, 0, canvas.width, canvas.height);
          setCanvasDimensions({ width: img.width, height: img.height }); // Trigger redraw after ref is ready
          resolve();
        };
        img.onerror = (e) => reject(new Error('Failed to load image object'));
      });

      if (maskBase64) {
        const maskImg = new Image();
        if (maskBase64.startsWith('data:image')) {
          maskImg.src = maskBase64;
        } else {
          maskImg.src = `data:image/png;base64,${maskBase64}`;
        }

        await new Promise((resolve, reject) => {
          maskImg.onload = () => {
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
            resolve();
          };
          maskImg.onerror = (e) => reject(e);
        });
      } else {
        maskDataRef.current = new ImageData(canvas.width, canvas.height);
        originalMaskRef.current = new ImageData(canvas.width, canvas.height);
      }

      setUndoStack([]);
      setRedoStack([]);
      setZoom(1.0);
      setOffset({ x: 0, y: 0 });
      // Redraw will be triggered by hooks
    } catch (error) {
      console.error('Error loading images:', error);
      message.error('Failed to load images');
    }
  };

  const drawCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas || !imageDataRef.current) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.putImageData(imageDataRef.current, 0, 0);

    if (showMask && maskDataRef.current) {
      const tempCanvas = document.createElement('canvas');
      tempCanvas.width = canvas.width;
      tempCanvas.height = canvas.height;
      const tempCtx = tempCanvas.getContext('2d');
      const overlayData = createMaskOverlay(maskDataRef.current);
      tempCtx.putImageData(overlayData, 0, 0);
      ctx.drawImage(tempCanvas, 0, 0);
    }
  };

  const handleMinimapClick = (e) => {
    const canvas = minimapRef.current;
    if (!canvas || !canvasDimensions.width) return;

    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const ix = (mx / rect.width) * canvasDimensions.width;
    const iy = (my / rect.height) * canvasDimensions.height;

    setOffset({
      x: -(ix - canvasDimensions.width / 2) * zoom,
      y: -(iy - canvasDimensions.height / 2) * zoom
    });
  };

  const drawMinimap = () => {
    const minimapCanvas = minimapRef.current;
    const container = containerRef.current;
    if (!minimapCanvas || !imageDataRef.current || !container || canvasDimensions.width === 0) return;

    const ctx = minimapCanvas.getContext('2d');
    const width = minimapCanvas.width;
    const height = minimapCanvas.height;

    // Ensure internal canvas size matches DOM size for sharpness
    if (minimapCanvas.width !== minimapCanvas.clientWidth || minimapCanvas.height !== minimapCanvas.clientHeight) {
      minimapCanvas.width = minimapCanvas.clientWidth || 240;
      minimapCanvas.height = minimapCanvas.clientHeight || 180;
    }

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = '#000'; // Fallback background
    ctx.fillRect(0, 0, width, height);

    // Draw base image scale
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = canvasDimensions.width;
    tempCanvas.height = canvasDimensions.height;
    const tempCtx = tempCanvas.getContext('2d');
    tempCtx.putImageData(imageDataRef.current, 0, 0);
    ctx.drawImage(tempCanvas, 0, 0, width, height);

    // Draw mask on minimap
    if (showMask && maskDataRef.current) {
      const maskOverlay = createMaskOverlay(maskDataRef.current);
      tempCtx.putImageData(maskOverlay, 0, 0);
      ctx.drawImage(tempCanvas, 0, 0, width, height);
    }

    // Draw viewport rectangle
    const scaleX = width / canvasDimensions.width;
    const scaleY = height / canvasDimensions.height;

    const viewWidth = container.clientWidth / zoom;
    const viewHeight = container.clientHeight / zoom;
    const viewX = (canvasDimensions.width / 2) - (offset.x / zoom) - (viewWidth / 2);
    const viewY = (canvasDimensions.height / 2) - (offset.y / zoom) - (viewHeight / 2);

    ctx.strokeStyle = '#ff4d4f';
    ctx.lineWidth = 2;
    ctx.strokeRect(viewX * scaleX, viewY * scaleY, viewWidth * scaleX, viewHeight * scaleY);
    ctx.fillStyle = 'rgba(255, 77, 79, 0.2)';
    ctx.fillRect(viewX * scaleX, viewY * scaleY, viewWidth * scaleX, viewHeight * scaleY);
  };

  const createMaskOverlay = (maskData) => {
    const width = maskData.width;
    const height = maskData.height;
    const overlay = new ImageData(width, height);
    for (let i = 0; i < maskData.data.length; i += 4) {
      if (maskData.data[i] > 0) {
        overlay.data[i] = 255; overlay.data[i + 1] = 255; overlay.data[i + 2] = 255; overlay.data[i + 3] = 180;
      } else {
        overlay.data[i] = 0; overlay.data[i + 1] = 0; overlay.data[i + 2] = 0; overlay.data[i + 3] = 0;
      }
    }
    return overlay;
  };

  const saveToUndoStack = () => {
    if (!maskDataRef.current) return;
    const maskCopy = new ImageData(new Uint8ClampedArray(maskDataRef.current.data), maskDataRef.current.width, maskDataRef.current.height);
    setUndoStack(prev => [...prev, maskCopy]);
    setRedoStack([]);
  };

  const handleUndo = () => {
    if (undoStack.length === 0) return;
    const previousState = undoStack[undoStack.length - 1];
    const currentCopy = new ImageData(new Uint8ClampedArray(maskDataRef.current.data), maskDataRef.current.width, maskDataRef.current.height);
    setRedoStack(prev => [...prev, currentCopy]);
    maskDataRef.current = new ImageData(new Uint8ClampedArray(previousState.data), previousState.width, previousState.height);
    setUndoStack(prev => prev.slice(0, -1));
    drawCanvas();
    drawMinimap();
  };

  const handleRedo = () => {
    if (redoStack.length === 0) return;
    const nextState = redoStack[redoStack.length - 1];
    const currentCopy = new ImageData(new Uint8ClampedArray(maskDataRef.current.data), maskDataRef.current.width, maskDataRef.current.height);
    setUndoStack(prev => [...prev, currentCopy]);
    maskDataRef.current = new ImageData(new Uint8ClampedArray(nextState.data), nextState.width, nextState.height);
    setRedoStack(prev => prev.slice(0, -1));
    drawCanvas();
    drawMinimap();
  };

  const getCanvasCoordinates = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();

    // Calculate position relative to the transformed canvas
    const x = (e.clientX - rect.left) * (canvas.width / rect.width);
    const y = (e.clientY - rect.top) * (canvas.height / rect.height);

    return { x: Math.floor(x), y: Math.floor(y) };
  };

  const drawBrush = (x, y) => {
    if (!maskDataRef.current) return;
    const currentBrushSize = tool === 'paint' ? paintBrushSize : eraseBrushSize;
    const radius = Math.floor(currentBrushSize / 2);
    const value = tool === 'paint' ? 255 : 0;
    const data = maskDataRef.current.data;
    const width = maskDataRef.current.width;
    for (let dy = -radius; dy <= radius; dy++) {
      for (let dx = -radius; dx <= radius; dx++) {
        if (dx * dx + dy * dy <= radius * radius) {
          const px = x + dx;
          const py = y + dy;
          if (px >= 0 && px < width && py >= 0 && py < maskDataRef.current.height) {
            const idx = (py * width + px) * 4;
            data[idx] = value; data[idx + 1] = value; data[idx + 2] = value; data[idx + 3] = 255;
          }
        }
      }
    }
    drawCanvas();
    drawMinimap();
  };

  const handleMouseDown = (e) => {
    if (tool === 'hand' || e.button === 1 || (e.button === 0 && e.ctrlKey)) {
      setIsPanning(true);
      setPanStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
      return;
    }
    if (e.button !== 0) return;
    const coords = getCanvasCoordinates(e);
    if (!coords) return;
    saveToUndoStack();
    setIsDrawing(true);
    drawBrush(coords.x, coords.y);
  };

  const handleMouseMove = (e) => {
    const container = containerRef.current;
    if (container) {
      const rect = container.getBoundingClientRect();
      // Use client coordinates directly for more speed-resilient tracking
      setMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    }

    const coords = getCanvasCoordinates(e);
    if (coords) setCursorPos(coords);

    if (isPanning) {
      setOffset({ x: e.clientX - panStart.x, y: e.clientY - panStart.y });
      return;
    }
    if (!isDrawing) return;
    if (coords) drawBrush(coords.x, coords.y);
  };

  const handleMouseUp = () => {
    setIsDrawing(false);
    setIsPanning(false);
  };

  const handleWheel = (e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    const newZoom = Math.max(0.1, Math.min(10.0, zoom + delta));

    // Zoom-to-cursor logic
    const rect = canvasRef.current.parentElement.getBoundingClientRect();
    const mouseX = e.clientX - rect.left - rect.width / 2;
    const mouseY = e.clientY - rect.top - rect.height / 2;

    // New offset to keep cursor over same image point
    const zoomRatio = newZoom / zoom;
    const newOffsetX = mouseX - (mouseX - offset.x) * zoomRatio;
    const newOffsetY = mouseY - (mouseY - offset.y) * zoomRatio;

    setZoom(newZoom);
    setOffset({ x: newOffsetX, y: newOffsetY });
  };

  const handleSave = () => {
    if (!maskDataRef.current) {
      message.error('No mask data to save'); return;
    }
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = maskDataRef.current.width;
    tempCanvas.height = maskDataRef.current.height;
    const tempCtx = tempCanvas.getContext('2d');
    tempCtx.putImageData(maskDataRef.current, 0, 0);
    const mBase64 = tempCanvas.toDataURL('image/png').split(',')[1];
    if (onSave) onSave(mBase64);
  };

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      switch (e.key.toLowerCase()) {
        case 'p': setTool('paint'); break;
        case 'e': setTool('erase'); break;
        case 'h': setTool('hand'); break;
        case 'z': if (e.ctrlKey || e.metaKey) { e.preventDefault(); if (e.shiftKey) handleRedo(); else handleUndo(); } break;
        case 'y': if (e.ctrlKey || e.metaKey) { e.preventDefault(); handleRedo(); } break;
        case 's': if (e.ctrlKey || e.metaKey) { e.preventDefault(); handleSave(); } break;
        case 'a': case 'arrowleft': if (onPrevious) onPrevious(); break;
        case 'd': case 'arrowright': if (onNext) onNext(); break;
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [undoStack, redoStack, onNext, onPrevious, tool, paintBrushSize, eraseBrushSize, zoom, offset]);

  const activeBrushSize = tool === 'erase' ? eraseBrushSize : paintBrushSize;
  const setBrushSize = tool === 'erase' ? setEraseBrushSize : setPaintBrushSize;

  return (
    <div style={{ display: 'flex', height: '100%', gap: '16px', overflow: 'hidden' }}>
      {/* Left Panel - Tools */}
      <Card
        title="Tools"
        style={{ width: '280px', height: '100%' }}
        bodyStyle={{ height: 'calc(100% - 40px)', overflowY: 'auto', padding: '12px' }}
        size="small"
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>Minimap</div>
            <div
              style={{
                background: '#eee',
                border: '1px solid #d9d9d9',
                position: 'relative',
                width: '240px', // Adjusted for sidebar width 280-padding
                height: '180px',
                margin: '0 auto',
                borderRadius: '4px',
                overflow: 'hidden',
                cursor: 'crosshair',
                display: (canvasDimensions.width > 0) ? 'block' : 'none'
              }}
              onClick={handleMinimapClick}
            >
              <canvas
                ref={minimapRef}
                width={240}
                height={180}
                style={{ width: '100%', height: '100%', display: 'block' }}
              />
              <div style={{ position: 'absolute', bottom: '4px', left: '4px', background: 'rgba(0,0,0,0.5)', color: 'white', fontSize: '10px', padding: '0 4px', borderRadius: '3px', pointerEvents: 'none', opacity: 0.7 }}>Minimap (Click to Jump)</div>
            </div>
          </div>

          <Divider style={{ margin: '8px 0' }} />

          <div>
            <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>Mode</div>
            <Space>
              <Tooltip title="Paint (P)">
                <Button type={tool === 'paint' ? 'primary' : 'default'} icon={<EditOutlined />} onClick={() => setTool('paint')} />
              </Tooltip>
              <Tooltip title="Erase (E)">
                <Button type={tool === 'erase' ? 'primary' : 'default'} icon={<ClearOutlined />} onClick={() => setTool('erase')} />
              </Tooltip>
              <Tooltip title="Hand (H)">
                <Button type={tool === 'hand' ? 'primary' : 'default'} icon={<DragOutlined />} onClick={() => setTool('hand')} />
              </Tooltip>
            </Space>
          </div>

          {(tool === 'paint' || tool === 'erase') && (
            <div>
              <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>{tool === 'erase' ? 'Erase' : 'Paint'} Size</div>
              <Slider min={1} max={64} value={activeBrushSize} onChange={setBrushSize} />
              <InputNumber min={1} max={64} value={activeBrushSize} onChange={setBrushSize} style={{ width: '100%' }} />
            </div>
          )}

          <Divider style={{ margin: '8px 0' }} />

          <div>
            <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>History</div>
            <Space>
              <Tooltip title="Undo (Ctrl+Z)"><Button icon={<UndoOutlined />} onClick={handleUndo} disabled={undoStack.length === 0}>Undo</Button></Tooltip>
              <Tooltip title="Redo (Ctrl+Shift+Z)"><Button icon={<RedoOutlined />} onClick={handleRedo} disabled={redoStack.length === 0}>Redo</Button></Tooltip>
            </Space>
          </div>

          <div>
            <Button icon={showMask ? <EyeInvisibleOutlined /> : <EyeOutlined />} onClick={() => setShowMask(!showMask)} block>{showMask ? 'Hide Mask' : 'Show Mask'}</Button>
          </div>

          <div>
            <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>Zoom ({Math.round(zoom * 100)}%)</div>
            <Space>
              <Button icon={<ZoomOutOutlined />} onClick={() => setZoom(prev => Math.max(0.1, prev - 0.1))} />
              <Button onClick={() => { setZoom(1.0); setOffset({ x: 0, y: 0 }); }}>Reset</Button>
              <Button icon={<ZoomInOutlined />} onClick={() => setZoom(prev => Math.min(10.0, prev + 0.1))} />
            </Space>
          </div>

          <Divider style={{ margin: '8px 0' }} />

        </Space>
      </Card>

      {/* Center - Canvas */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '16px', height: '100%' }}>
        {totalLayers > 1 && (
          <Card size="small">
            <Space style={{ width: '100%', justifyContent: 'space-between' }}>
              <Button icon={<LeftOutlined />} onClick={onPrevious} disabled={currentLayer === 0}>Previous (A)</Button>
              <span style={{ fontWeight: 'bold' }}>{layerName || `Layer ${currentLayer + 1}`} / {totalLayers}</span>
              <Button icon={<RightOutlined />} onClick={onNext} disabled={currentLayer === totalLayers - 1}>Next (D)</Button>
            </Space>
          </Card>
        )}

        <Card style={{ flex: 1, overflow: 'hidden' }} bodyStyle={{ height: '100%', position: 'relative', display: 'flex', justifyContent: 'center', alignItems: 'center', cursor: (tool === 'hand' || isPanning) ? 'grabbing' : (tool === 'paint' || tool === 'erase' ? 'none' : 'default'), background: '#f5f5f5', padding: 0 }}>

          <div
            ref={containerRef}
            style={{
              position: 'relative',
              width: '100%',
              height: '100%',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              overflow: 'hidden'
            }}
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          >
            <canvas
              ref={canvasRef}
              style={{
                border: '1px solid #d9d9d9',
                transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})`,
                transformOrigin: 'center',
                imageRendering: 'pixelated',
                boxShadow: '0 0 20px rgba(0,0,0,0.1)'
              }}
            />
            {/* Custom Cursor */}
            {/* Cursor SVG overlay - follows mousePos directly for absolute tracking */}
            {!isPanning && (tool === 'paint' || tool === 'erase') && mousePos && (
              <div style={{
                position: 'absolute',
                left: mousePos.x,
                top: mousePos.y,
                width: activeBrushSize * zoom,
                height: activeBrushSize * zoom,
                border: tool === 'paint' ? '2px solid #1890ff' : '2px dashed #ff4d4f',
                boxShadow: tool === 'erase' ? '0 0 0 1px white' : 'none', // High contrast for eraser
                borderRadius: '50%',
                pointerEvents: 'none',
                transform: 'translate(-50%, -50%)',
                zIndex: 1001
              }} />
            )}
          </div>
        </Card>
      </div>
    </div>
  );
});

export default ProofreadingEditor;

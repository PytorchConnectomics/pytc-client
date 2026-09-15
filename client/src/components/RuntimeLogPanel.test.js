import React from 'react';
import { render, screen } from '@testing-library/react';
import RuntimeLogPanel from './RuntimeLogPanel';

test('completed CPU jobs are not reported as failed for CUDA memory warnings', () => {
  render(<RuntimeLogPanel title="Training" runtime={{phase:'finished', exitCode:0,
    text:'UserWarning: pin_memory enabled but no CUDA accelerator available'}} />);
  expect(screen.queryByText('Needs attention')).toBeNull();
  expect(screen.getByText('Completed')).toBeTruthy();
});

test('nonzero exits remain failures even without a traceback', () => {
  render(<RuntimeLogPanel title="Training" runtime={{phase:'finished', exitCode:1, text:''}} />);
  expect(screen.getByText('Needs attention')).toBeTruthy();
});

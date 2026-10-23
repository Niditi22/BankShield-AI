// @vitest-environment jsdom
import React from 'react';
import {describe,it,expect,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react';
import {PhotoCapture} from './Capture';
afterEach(()=>{cleanup();vi.restoreAllMocks()});
describe('Manual enrollment camera',()=>{
 it('opens on request, captures only after click, and stops the camera',async()=>{
  const stop=vi.fn(),getUserMedia=vi.fn().mockResolvedValue({getTracks:()=>[{stop}]});
  Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia},configurable:true});
  vi.stubGlobal('requestAnimationFrame',fn=>setTimeout(fn,0));
  vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue({drawImage:vi.fn()});
  vi.spyOn(HTMLCanvasElement.prototype,'toBlob').mockImplementation(cb=>cb(new Blob(['photo'],{type:'image/png'})));
  const change=vi.fn();const {container}=render(<PhotoCapture angle="front" onChange={change}/>);
  expect(getUserMedia).not.toHaveBeenCalled();expect(container.querySelector('input[type=file]')).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'Open camera'}));
  await screen.findByRole('button',{name:'Click photo'});expect(change).not.toHaveBeenCalled();
  const video=container.querySelector('video');Object.defineProperty(video,'videoWidth',{value:640});Object.defineProperty(video,'videoHeight',{value:480});
  fireEvent.click(screen.getByRole('button',{name:'Click photo'}));
  await waitFor(()=>expect(change).toHaveBeenCalledOnce());expect(change.mock.calls[0][0].type).toBe('image/png');expect(stop).toHaveBeenCalledOnce();
 });
 it('shows a useful error if permission is denied',async()=>{
  Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia:vi.fn().mockRejectedValue(Error('Permission denied'))},configurable:true});
  render(<PhotoCapture angle="left" onChange={vi.fn()}/>);fireEvent.click(screen.getByRole('button',{name:'Open camera'}));
  expect(await screen.findByText(/Camera could not start/)).toBeTruthy();
 });
 it('releases an active camera when leaving the screen',async()=>{
  const stop=vi.fn();Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia:vi.fn().mockResolvedValue({getTracks:()=>[{stop}]})},configurable:true});
  const {unmount}=render(<PhotoCapture angle="right" onChange={vi.fn()}/>);fireEvent.click(screen.getByRole('button',{name:'Open camera'}));
  await screen.findByRole('button',{name:'Click photo'});unmount();expect(stop).toHaveBeenCalledOnce();
 });
});

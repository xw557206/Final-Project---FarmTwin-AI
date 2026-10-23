import React from 'react';

export type WeatherKind = 'sunny'|'partly-cloudy'|'cloudy'|'rain'|'thunderstorm'|'snow'|'frost'|'wind'|'heat'|'alert';

export function WeatherIcon({kind='sunny', size=42}:{kind?:WeatherKind;size?:number}) {
  const color = kind==='alert' || kind==='heat' ? '#b9574e' : kind==='frost' || kind==='snow' ? '#79abc2' : kind==='rain' || kind==='thunderstorm' ? '#5d83a0' : '#d9a640';
  return <svg width={size} height={size} viewBox="0 0 48 48" className="weather-icon" aria-hidden="true" shapeRendering="crispEdges">
    {kind==='sunny' || kind==='heat' ? <><path d="M20 7h8v5h-8zM20 36h8v5h-8zM7 20h5v8H7zm29 0h5v8h-5zM11 11h5v5h-5zm21 21h5v5h-5zM32 11h5v5h-5zM11 32h5v5h-5z" fill={color}/><circle cx="24" cy="24" r="10" fill={color}/></> : null}
    {kind==='partly-cloudy' && <><circle cx="30" cy="17" r="8" fill="#e7b84e"/><path d="M10 25h25v12H10z" fill="#d6e4e4"/><path d="M15 20h12v5H15z" fill="#d6e4e4"/><path d="M8 29h29v8H8z" fill="#b9d0d1"/></>}
    {kind==='cloudy' && <><path d="M9 25h30v12H9z" fill="#aebfc3"/><path d="M15 19h18v6H15z" fill="#cbd9d8"/><path d="M21 14h9v6h-9z" fill="#dce5e0"/></>}
    {kind==='rain' || kind==='thunderstorm' ? <><path d="M9 14h25v17H9z" fill="#9eb7c1"/><path d="M15 9h15v6H15z" fill="#c9d9d8"/><path d="M14 35h3v7h-3zm9-3h3v10h-3zm9 3h3v7h-3z" fill={color}/>{kind==='thunderstorm'&&<path d="M24 26h6l-5 8h4l-8 10 3-9h-4z" fill="#e0b43f"/>}</> : null}
    {kind==='snow' || kind==='frost' ? <><path d="M9 14h25v16H9z" fill="#b8d5df"/><path d="M15 9h15v6H15z" fill="#e9f4f2"/><path d="M15 34h4v4h-4zm8-4h4v4h-4zm8 4h4v4h-4z" fill="#fff"/></> : null}
    {kind==='wind' ? <><path d="M7 16h25v4H7zm10 8h24v4H17zM7 32h18v4H7z" fill={color}/><circle cx="34" cy="18" r="4" fill="#c7d8d1"/></> : null}
    {kind==='alert' ? <><path d="M24 6 43 41H5z" fill="#b9574e"/><path d="M22 16h4v13h-4zm0 17h4v4h-4z" fill="#fff0c7"/></> : null}
  </svg>;
}

export function weatherKind(text:string|undefined):WeatherKind { const value=(text||'').toLowerCase(); if(value.includes('thunder')) return 'thunderstorm'; if(value.includes('snow')||value.includes('sleet')) return 'snow'; if(value.includes('rain')||value.includes('shower')) return 'rain'; if(value.includes('cloud')) return value.includes('partly')?'partly-cloudy':'cloudy'; return 'sunny'; }

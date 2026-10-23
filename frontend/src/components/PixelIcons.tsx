import React from 'react';

export type PixelKind = 'tomato'|'lettuce'|'spinach'|'carrot'|'potato'|'strawberry'|'corn'|'cucumber'|'milk'|'cow'|'chicken'|'chick'|'rooster'|'egg'|'carton'|'coop'|'nest'|'feedsack'|'trough'|'basket'|'fence'|'greenhouse'|'barn'|'storage'|'shed'|'crate'|'farmer'|'worker'|'tractor'|'buyer'|'envelope'|'advisor'|'field';

const colors: Record<PixelKind, [string,string]> = {
  tomato:['#d75b4d','#f5b28b'], lettuce:['#78a96d','#d6e9ad'], spinach:['#477e58','#a9cf8e'], carrot:['#e88c3d','#f8cf84'], potato:['#bd8a52','#efd19b'], strawberry:['#d95868','#f6c4ad'], corn:['#e0b43f','#f8e69b'], cucumber:['#55966c','#b6d59b'], milk:['#f6f0dc','#8bb7cb'], cow:['#f4ead7','#5f4d43'], chicken:['#a97852','#f1d2a0'], chick:['#edc354','#fff0a8'], rooster:['#a96c4d','#d94642'], egg:['#fff4d5','#e5c68d'], carton:['#a4bad0','#e8f0f3'], coop:['#b56d4e','#efd09b'], nest:['#ad8250','#e9c77b'], feedsack:['#b8a06d','#f0dda8'], trough:['#7b9a9e','#c8dfe0'], basket:['#bd8751','#f0c779'], fence:['#9d754f','#d8b77b'], greenhouse:['#78a9a0','#d0ead0'], barn:['#b9574e','#f4c38d'], storage:['#9b8265','#ead4a8'], shed:['#6c8068','#c5d3ad'], crate:['#b77c49','#edbd74'], farmer:['#547b5d','#e0a772'], worker:['#6b80a0','#f0b486'], tractor:['#c86d3d','#f0c15b'], buyer:['#577c98','#d5e6ed'], envelope:['#7d906e','#e5eed8'], advisor:['#6d7eaa','#dfd5f0'], field:['#78a25e','#c9db97']
};

export function PixelIcon({kind, size=32, className=''}:{kind:PixelKind;size?:number;className?:string}) {
  const [primary, light] = colors[kind];
  const isRound = ['tomato','strawberry','potato','milk','cow','chicken','chick','rooster','egg','advisor','buyer'].includes(kind);
  return <svg className={`pixel-icon ${className}`} width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" shapeRendering="crispEdges">
    <path d="M4 6h24v20H4z" fill="#203d31" opacity=".08"/>
    {isRound && <path d="M9 7h14v3h4v12h-4v4H9v-4H5V10h4z" fill={primary}/>} 
    {kind==='tomato' && <><path d="M14 8h4V4h4v5h-3l3 3-5-2-5 2 3-3h-3V6h2z" fill="#5d8b52"/><path d="M9 14h14v7H9z" fill={light}/></>}
    {kind==='strawberry' && <><path d="M12 7h8v3h4v4H8v-4h4z" fill="#5d8b52"/><path d="M10 16h12v6H10z" fill={light}/><path d="M13 17h2v2h-2zm5 2h2v2h-2z" fill="#fff1bd"/></>}
    {kind==='potato' && <path d="M10 11h12v3h4v8h-4v4H10v-3H7v-8h3z" fill={light}/>} 
    {kind==='milk' && <><path d="M10 7h12v4h2v14H8V11h2z" fill="#fff"/><path d="M10 15h14v4H10z" fill={light}/><path d="M13 8h6" stroke="#8bb7cb" strokeWidth="2"/></>}
    {kind==='cow' && <><path d="M7 11h18v12H7z" fill={light}/><path d="M10 14h5v4h-5zm9 5h4v4h-4z" fill={primary}/><path d="M4 10h5v5H4zm19 0h5v5h-5z" fill={primary}/><path d="M11 23v4m10-4v4" stroke="#5f4d43" strokeWidth="2"/></>}
    {['chicken','chick','rooster'].includes(kind) && <><path d="M8 13h15v11H8z" fill={light}/><path d="M5 14h7v7H5z" fill={primary}/><path d="M20 10h5v5h-5z" fill={primary}/><path d="M23 8h3v3h-3M12 24v4m8-4v4" stroke={primary} strokeWidth="2"/><path d="M25 13h4v3h-4z" fill="#d88a3d"/>{kind!=='chick'&&<path d="M13 9h3v4h-3z" fill={kind==='rooster'?'#d94642':'#c77b58'}/>}</>}
    {kind==='egg' && <path d="M16 5c5 0 9 7 9 13 0 6-4 9-9 9s-9-3-9-9c0-6 4-13 9-13z" fill={light}/>} 
    {kind==='carton' && <><path d="M5 11h22v16H5z" fill={primary}/><path d="M8 7h5v5H8zm7 0h5v5h-5zm7 0h3v5h-3z" fill={light}/><path d="M5 16h22" stroke="#fff4d6" strokeWidth="2"/></>}
    {kind==='coop' && <><path d="M4 14 16 5l12 9v14H4z" fill={primary}/><path d="M9 16h14v12H9z" fill={light}/><path d="M14 20h5v8h-5z" fill="#7f533a"/><path d="M6 12h20" stroke="#784837" strokeWidth="2"/></>}
    {kind==='nest' && <><path d="M6 18h20v9H6z" fill={primary}/><path d="M8 15h16v5H8z" fill={light}/><path d="M11 11h4v5h-4zm7 1h4v4h-4z" fill="#fff4d6"/></>}
    {kind==='feedsack' && <><path d="M9 7h14l3 5v15H6V12z" fill={primary}/><path d="M11 13h10v4H11z" fill={light}/><path d="M13 20h6v3h-6z" fill="#6e684a"/></>}
    {kind==='trough' && <><path d="M5 16h22v10H5z" fill={primary}/><path d="M8 13h16v6H8z" fill={light}/><path d="M9 27v3m14-3v3" stroke="#536b63" strokeWidth="2"/></>}
    {kind==='basket' && <><path d="M6 13h20v14H6z" fill={primary}/><path d="M10 13c0-8 12-8 12 0" fill="none" stroke={light} strokeWidth="3"/><path d="M9 17h14" stroke={light} strokeWidth="2"/></>}
    {kind==='fence' && <><path d="M5 8h4v20H5zm18 0h4v20h-4z" fill={primary}/><path d="M7 12h18v4H7zm0 9h18v4H7z" fill={light}/></>}
    {['lettuce','spinach','field'].includes(kind) && <><path d="M7 23h18v3H7z" fill="#6f914f"/><path d="M10 19h12v5H10z" fill={primary}/><path d="M13 12h3v8h-3zm5-3h3v11h-3z" fill={light}/></>}
    {kind==='carrot' && <><path d="M13 14h7v13h-7z" fill={primary}/><path d="M10 8h4v7h-4zm5-4h3v11h-3zm4 6h4v5h-4z" fill="#6d9b5c"/></>}
    {kind==='corn' && <><path d="M11 9h10v17H11z" fill={light}/><path d="M8 8h4v13H8zm12-2h4v13h-4z" fill="#77a960"/><path d="M14 13h4v3h-4z" fill={primary}/></>}
    {kind==='cucumber' && <><path d="M9 8h14v5h3v9H6v-9h3z" fill={primary}/><path d="M12 11h3v3h-3zm7 5h3v3h-3z" fill={light}/></>}
    {['greenhouse','barn','storage','shed'].includes(kind) && <><path d="M5 13 16 5l11 8v14H5z" fill={primary}/><path d="M9 16h14v8H9z" fill={light}/><path d="M14 19h4v8h-4z" fill="#fff4d6"/></>}
    {kind==='crate' && <><path d="M6 10h20v17H6z" fill={primary}/><path d="M6 14h20M11 10v17M21 10v17" stroke={light} strokeWidth="2"/></>}
    {['farmer','worker'].includes(kind) && <><path d="M9 12h14v13H9z" fill={primary}/><path d="M11 7h10v7H11z" fill="#f0b486"/><path d="M8 6h16v4H8z" fill={light}/><path d="M12 25v4m8-4v4" stroke="#4f6149" strokeWidth="3"/></>}
    {kind==='tractor' && <><path d="M8 14h13v10H8z" fill={primary}/><path d="M13 8h7v7h-7zM17 8h4l4 6h-8z" fill={light}/><circle cx="10" cy="26" r="4" fill="#344b3b"/><circle cx="24" cy="25" r="3" fill="#344b3b"/><path d="M4 16h5v4H4z" fill="#f2d56c"/></>}
    {kind==='buyer' && <><path d="M7 11h18v16H7z" fill={primary}/><path d="M10 7h12v7H10z" fill={light}/><path d="M12 17h8v3h-8z" fill="#fff4d6"/></>}
    {kind==='advisor' && <><path d="M8 10h16v15H8z" fill={primary}/><path d="M12 15h3v3h-3zm5 0h3v3h-3z" fill={light}/><path d="M14 4h4v6h-4z" fill={light}/></>}
  </svg>;
}

export function ProductAvatar({crop,size=28}:{crop:string;size?:number}) { const key=(crop.toLowerCase().replace(' ','')==='sweetcorn'?'corn':crop.toLowerCase().replace(' ','') as PixelKind); return <span className="product-avatar"><PixelIcon kind={key in colors?key:'field'} size={size}/></span>; }
export function FacilityIcon({type,size=30}:{type:string;size?:number}) { const value=type.toLowerCase(); const key=value.includes('green')?'greenhouse':value.includes('barn')?'barn':value.includes('storage')?'storage':value.includes('coop')||value.includes('poultry')||value.includes('run')?'coop':'shed'; return <PixelIcon kind={key} size={size}/>; }


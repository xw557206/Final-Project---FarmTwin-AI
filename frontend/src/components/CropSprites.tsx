import React from 'react';

export type CropStage = 'SEED' | 'SPROUT' | 'GROWING' | 'MATURE' | 'HARVEST_READY';

type Props = { cropId?: string; stage?: CropStage; x?: number; y?: number; scale?: number; label?: string };

const stageRank: Record<CropStage, number> = { SEED: 0, SPROUT: 1, GROWING: 2, MATURE: 3, HARVEST_READY: 4 };

export function cropStage(planting?: string, harvest?: string, asOf = new Date(), maturityDays = 60): CropStage {
  if (!planting) return 'SEED';
  const planted = new Date(`${planting}T12:00:00`);
  const harvestDate = harvest ? new Date(`${harvest}T12:00:00`) : new Date(planted.getTime() + maturityDays * 86400000);
  const elapsed = Math.floor((asOf.getTime() - planted.getTime()) / 86400000);
  if (elapsed < 0) return 'SEED';
  if (asOf >= harvestDate) return 'HARVEST_READY';
  const fraction = elapsed / Math.max(1, maturityDays || Math.floor((harvestDate.getTime() - planted.getTime()) / 86400000));
  if (fraction < .18) return 'SPROUT';
  if (fraction < .65) return 'GROWING';
  return 'MATURE';
}

function Soil({ x = 0, y = 0 }: { x?: number; y?: number }) {
  return <g transform={`translate(${x} ${y})`}><path d="M3 27h26" stroke="#75553b" strokeWidth="2"/><path d="M5 29h6m5 0h6m4 0h3" stroke="#a8794b" strokeWidth="1"/></g>;
}

function SpriteArt({ crop, stage }: { crop: string; stage: CropStage }) {
  const mature = stageRank[stage] >= stageRank.MATURE;
  const ready = stage === 'HARVEST_READY';
  if (crop === 'tomatoes') return <><Soil/><path d="M16 27V12M16 17l-6-5m6 8 7-6M10 12 7 8m13 2 3-5" stroke="#39754b" strokeWidth="2"/><path d="M5 8h5v3H5zM21 5h5v3h-5zM8 15h5v3H8z" fill="#6ba257"/>{mature&&<><path d="M5 13h5v5H5zM20 11h5v5h-5zM11 20h5v5h-5z" fill="#cf4e43"/><path d="M7 13h2M22 11h2" stroke="#f39b62" strokeWidth="1"/></>}</>;
  if (crop === 'lettuce') return <><Soil/><path d="M16 27V20" stroke="#578a4d" strokeWidth="2"/><path d="M5 23c0-6 5-9 9-4-1-7 7-8 8-2 5-3 9 3 5 7-5 3-16 3-22-1z" fill="#77ad5c" stroke="#3d7849" strokeWidth="1"/><path d="M10 22c4-4 8-4 13 1M13 18c1 3 1 5 1 7" stroke="#c3df91" strokeWidth="1"/></>;
  if (crop === 'spinach') return <><Soil/><path d="M16 27V19" stroke="#315f3b" strokeWidth="2"/><path d="M15 21c-8 2-10-5-4-8 1 4 3 6 4 8zM17 20c8 2 10-5 4-9-1 4-3 6-4 9zM15 16c-5-2-4-8 1-9 2 4 1 7-1 9z" fill="#2f7046" stroke="#214d37" strokeWidth="1"/></>;
  if (crop === 'carrots') return <><Soil/><path d="M16 14v13M11 15l-3-5m8 5 4-7m-1 8 5-4" stroke="#548d4c" strokeWidth="2"/><path d="M12 22h5l-2 7h-3z" fill={ready ? '#e27932' : '#b9a06a'} stroke="#9b5c34" strokeWidth="1"/><path d="M20 22h5l-2 7h-3z" fill={ready ? '#e27932' : '#b9a06a'} stroke="#9b5c34" strokeWidth="1"/></>;
  if (crop === 'potatoes') return <><Soil/><path d="M16 26V13M16 18l-6-6m6 3 6-7" stroke="#4d8148" strokeWidth="2"/><path d="M7 12c3-4 6-3 8 1M18 9c3-4 7-1 7 2" fill="none" stroke="#72a65a" strokeWidth="2"/>{ready&&<><path d="M8 25h6v4H8zM19 25h6v4h-6z" fill="#b68755"/><path d="M9 26h2m9 1h2" stroke="#e3b276" strokeWidth="1"/></>}</>;
  if (crop === 'strawberries') return <><Soil/><path d="M16 26V19M9 25c1-5 5-7 7-3 2-4 7-2 7 3" stroke="#4e8b50" strokeWidth="2"/><path d="M8 20c3-4 6-3 8 0M18 20c2-4 6-3 8 1" fill="none" stroke="#6eaa57" strokeWidth="3"/>{mature&&<><path d="M7 21h5v5H7zM19 22h5v5h-5zM13 18h5v5h-5z" fill="#d6494d"/><path d="M9 22v1m12 1v1m-5-5v1" stroke="#ffe5a7" strokeWidth="1"/></>}</>;
  if (crop === 'corn') return <><Soil/><path d="M9 28V7M16 28V4M23 28V8" stroke="#4c8a4c" strokeWidth="3"/><path d="M9 12 4 8m12 5 5-7m2 9 6-5" stroke="#6da85a" strokeWidth="2"/>{mature&&<><path d="M12 15h4v8h-4zM19 17h4v8h-4z" fill="#e3b83e"/><path d="M13 17h2m5 2h2" stroke="#fff0a3" strokeWidth="1"/></>}</>;
  if (crop === 'cucumbers') return <><Soil/><path d="M4 24c5-8 10 1 15-7 3-4 6-4 9-7M10 22v-7m8 4v-7" fill="none" stroke="#438456" strokeWidth="2"/><path d="M8 13h5v3H8zM18 17h6v3h-6zM22 9h5v3h-5z" fill="#5ba56d"/><path d="M9 16h4M20 20h3" stroke="#afd484" strokeWidth="1"/></>;
  if (crop === 'apples') return <><Soil/><path d="M16 27V13M16 17 9 11m7 5 7-7" stroke="#674b37" strokeWidth="2"/><path d="M7 12c0-5 4-7 8-4 4-4 9-1 9 4 0 8-13 10-17 0z" fill="#5a9855" stroke="#356c43" strokeWidth="1"/>{mature&&<><circle cx="11" cy="11" r="2.5" fill="#d24d45"/><circle cx="20" cy="14" r="2.5" fill="#d24d45"/></>}</>;
  if (crop === 'pumpkins') return <><Soil/><path d="M16 25c-5-5-11 3-13-3m13 3c5-5 11 3 13-3M16 25V17" fill="none" stroke="#4b894e" strokeWidth="2"/>{mature&&<><path d="M9 21h7v7H9zM17 20h7v8h-7z" fill="#e47d2e" stroke="#a6542b" strokeWidth="1"/><path d="M12 21v7m8-8v8" stroke="#f5ae4f" strokeWidth="1"/></>}</>;
  return <><Soil/><path d="M16 27V14M10 21l6-7 6 7" stroke="#789663" strokeWidth="2"/><path d="M11 15h4v4h-4zM18 12h4v4h-4z" fill="#b6cc91"/></>;
}

export function CropSprite({ cropId, stage = 'GROWING', x = 0, y = 0, scale = 1, label }: Props) {
  const crop = ({
    'crop-tomatoes': 'tomatoes', 'crop-lettuce': 'lettuce', 'crop-spinach': 'spinach',
    'crop-carrots': 'carrots', 'crop-potatoes': 'potatoes', 'crop-strawberries': 'strawberries',
    'crop-corn': 'corn', 'crop-cucumbers': 'cucumbers', 'crop-apples': 'apples', 'crop-pumpkins': 'pumpkins',
  } as Record<string, string>)[cropId || ''] || 'unknown';
  return <g transform={`translate(${x} ${y}) scale(${scale})`} role="img" aria-label={label || `${crop} ${stage.toLowerCase()}`}>
    <rect x="1" y="1" width="30" height="30" fill="#fff7df" opacity=".08" />
    <SpriteArt crop={crop} stage={stage}/>
  </g>;
}

export function CropSpriteIcon({ cropId, stage = 'MATURE', size = 40 }: { cropId?: string; stage?: CropStage; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 32 32" shapeRendering="crispEdges" aria-hidden="true"><CropSprite cropId={cropId} stage={stage}/></svg>;
}

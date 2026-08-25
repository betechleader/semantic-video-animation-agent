import React, {useEffect, useState} from 'react';
import {continueRender, delayRender} from 'remotion';

export const ChineseFontLoader: React.FC<{fontDataUri?: string; children: React.ReactNode}> = ({fontDataUri, children}) => {
  const [handle] = useState(() => fontDataUri ? delayRender('Loading task-local Chinese font') : null);
  useEffect(() => {
    if (!fontDataUri || handle === null) return;
    let active = true;
    const load = async () => {
      try {
        const face = new FontFace('KnowledgeChinese', `url(${fontDataUri})`);
        const loaded = await face.load();
        if (active) document.fonts.add(loaded);
      } finally {
        continueRender(handle);
      }
    };
    load();
    return () => { active = false; };
  }, [fontDataUri, handle]);
  return <>{children}</>;
};

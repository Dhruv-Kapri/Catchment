// The one number formatter the panel, the B - A table and the demand legend share.
export const integer = (value) => (Math.round(value) || 0).toLocaleString("en-IN");   // || 0: a hair under zero rounds to -0
export const percent = (gap) => (gap > 0 && gap < 0.0005 ? "<0.1%" : `${(gap * 100).toFixed(1)}%`);   // a small gap must not read as proven
export const points = (value) => `${(value * 100).toFixed(1)} pp`;   // a difference of two percentages

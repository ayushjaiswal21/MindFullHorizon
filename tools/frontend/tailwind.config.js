/** Layout utilities only (flex, grid, spacing, sizing, text size, responsive display).
 *  Colour comes from static/css/site.css tokens, so every colour-bearing plugin is switched off. */
module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
    '!./static/js/**/*.min.js',
    '!./static/gen/**',
  ],
  theme: { extend: {} },
  corePlugins: {
    preflight: false, // site.css has its own reset
    container: false, // .container is defined in site.css
    backgroundColor: false, backgroundOpacity: false, backgroundImage: false, gradientColorStops: false,
    textColor: false, textOpacity: false, borderColor: false, borderOpacity: false,
    divideColor: false, divideOpacity: false, ringColor: false, ringOpacity: false,
    ringOffsetColor: false, ringWidth: false, ringOffsetWidth: false, placeholderColor: false,
    accentColor: false, caretColor: false, fill: false, stroke: false, boxShadow: false,
    boxShadowColor: false, outlineColor: false, textDecorationColor: false,
    animation: false, backdropFilter: false, blur: false, brightness: false, filter: false,
  },
};

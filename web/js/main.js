// Wiring: the lever panel and the map.
import { renderLevers } from "./levers.js";
import { createMap } from "./map.js";

renderLevers(document.getElementById("levers"));
const view = createMap("map");

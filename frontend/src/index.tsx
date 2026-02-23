import "./index.css";
import { render } from "react-dom";
import { App } from "./App";
import { applyTheme, getInitialTheme } from "./lib/theme";

applyTheme(getInitialTheme());

render(<App />, document.getElementById("root"));

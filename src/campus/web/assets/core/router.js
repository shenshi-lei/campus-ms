let navigateHandler = () => {};
let refreshHandler = () => {};

export function setRouterHandlers(handlers) {
  navigateHandler = handlers.navigate || navigateHandler;
  refreshHandler = handlers.refresh || refreshHandler;
}

export function gotoView(viewId) {
  navigateHandler(viewId);
}

export function refreshView() {
  refreshHandler();
}

/**
 * AnalysisDrawer is a thin wrapper around Renderer + GameState for now.
 * Kept minimal in Phase 1; logic remains in Renderer.renderAnalysisDrawer.
 */
export class AnalysisDrawer {
  constructor(renderer, gameState) {
    this.renderer = renderer;
    this.gameState = gameState;
  }

  updateAndRender(partialAnalysis, autoOpen = false) {
    this.gameState.updateAnalysis(partialAnalysis);
    this.renderer.renderAnalysisDrawer(this.gameState.analysis);
    if (autoOpen) {
      this.renderer.openDrawer(true);
    }
  }
}


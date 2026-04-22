import { MatchingModel } from './matching-model'

export interface DocumentType extends MatchingModel {
  template_json?: string | Record<string, unknown>
}
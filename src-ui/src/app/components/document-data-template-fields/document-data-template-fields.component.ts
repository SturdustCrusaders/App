import { Component, Input } from '@angular/core';

export interface TemplateField {
  name: string;
  template_name: string;
  field: string;
  regions: Array<{
    x0: number;
    x1: number;
    y0: number;
    y1: number;
    page: number;
  }>;
}

@Component({
  selector: 'pngx-document-template-fields',
  templateUrl: './document-data-template-fields.component.html',
  styleUrls: ['./document-data-template-fields.component.scss']
})
export class DocumentTemplateFieldsComponent {
  @Input() templateFields: TemplateField[] = [];
  
  getRegionDisplay(region: any): string {
    return `Page ${region.page}: (${region.x0}, ${region.y0}) to (${region.x1}, ${region.y1})`;
  }
}

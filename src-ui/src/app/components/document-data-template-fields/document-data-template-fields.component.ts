import { Component, Input, ChangeDetectionStrategy } from '@angular/core';

export interface TemplateField {
  name: string;
  template_name: string;
  field: string;
  value: string; 
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
  styleUrls: ['./document-data-template-fields.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  standalone: true
})
export class DocumentTemplateFieldsComponent {
  @Input() templateFields: TemplateField[] = [];
  
  getRegionDisplay(region: any): string {
    return `Page ${region.page}: (${region.x0}, ${region.y0}) to (${region.x1}, ${region.y1})`;
  }

  isFieldEmpty(value: string): boolean {
    return !value || value.trim() === '';
  }
}

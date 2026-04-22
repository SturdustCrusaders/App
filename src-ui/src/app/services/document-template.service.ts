import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { TemplateField } from '../components/document-data-template-fields/document-data-template-fields.component';

@Injectable({
  providedIn: 'root'
})
export class DocumentTemplateService {
  constructor(private http: HttpClient) {}

  getTemplateFieldsByDocumentType(documentTypeId: number): Observable<TemplateField[]> {
    return this.http.get<TemplateField[]>(
      `/api/document-types/${documentTypeId}/template-fields/`
    );
  }
}

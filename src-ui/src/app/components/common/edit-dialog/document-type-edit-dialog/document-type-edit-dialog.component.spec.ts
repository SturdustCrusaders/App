import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbActiveModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { of } from 'rxjs'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { SettingsService } from 'src/app/services/settings.service'
import { PermissionsFormComponent } from '../../input/permissions/permissions-form/permissions-form.component'
import { SelectComponent } from '../../input/select/select.component'
import { TextComponent } from '../../input/text/text.component'
import { EditDialogMode } from '../edit-dialog.component'
import { DocumentTypeEditDialogComponent } from './document-type-edit-dialog.component'

describe('DocumentTypeEditDialogComponent', () => {
  let component: DocumentTypeEditDialogComponent
  let settingsService: SettingsService
  let fixture: ComponentFixture<DocumentTypeEditDialogComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgSelectModule,
        NgbModule,
        DocumentTypeEditDialogComponent,
        IfPermissionsDirective,
        IfOwnerDirective,
        SelectComponent,
        TextComponent,
        PermissionsFormComponent,
      ],
      providers: [
        NgbActiveModal,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(DocumentTypeEditDialogComponent)
    settingsService = TestBed.inject(SettingsService)
    settingsService.currentUser = { id: 99, username: 'user99' }
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should support create and edit modes', () => {
    component.dialogMode = EditDialogMode.CREATE
    const createTitleSpy = jest.spyOn(component, 'getCreateTitle')
    const editTitleSpy = jest.spyOn(component, 'getEditTitle')
    fixture.detectChanges()
    expect(createTitleSpy).toHaveBeenCalled()
    expect(editTitleSpy).not.toHaveBeenCalled()
    component.dialogMode = EditDialogMode.EDIT
    fixture.detectChanges()
    expect(editTitleSpy).toHaveBeenCalled()
  })

  it('should persist template_json together with matching settings when saving document type edits', () => {
    component.dialogMode = EditDialogMode.EDIT
    ;(component as any).object = {
      id: 1,
      name: 'Default',
      match: 'invoice',
      matching_algorithm: 1,
      is_insensitive: true,
      template_json: {
        match: 'invoice',
        matching_algorithm: 1,
        is_insensitive: true,
        fields: [
          {
            name: 'field_1',
            regions: [
              {
                page: 1,
                x0: 0.1,
                y0: 0.2,
                x1: 0.3,
                y1: 0.4,
              },
            ],
          },
        ],
      },
    }

    component.objectForm.patchValue({
      name: 'Default',
      match: 'invoice-2026',
      matching_algorithm: 2,
      is_insensitive: true,
      template_json: JSON.stringify((component as any).object.template_json, null, 2),
    })

    const updateSpy = jest
      .spyOn(TestBed.inject(DocumentTypeService), 'update')
      .mockReturnValue(of({ id: 1 }))
    const closeSpy = jest.spyOn(TestBed.inject(NgbActiveModal), 'close')

    component.save()

    expect(updateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        match: 'invoice-2026',
        matching_algorithm: 2,
        template_json: expect.objectContaining({
          match: 'invoice-2026',
          matching_algorithm: 2,
          is_insensitive: true,
        }),
      })
    )
    expect(closeSpy).toHaveBeenCalled()
  })
})

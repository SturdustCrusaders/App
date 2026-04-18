import { Component, inject } from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { DocumentType } from 'src/app/data/document-type'
import { DEFAULT_MATCHING_ALGORITHM } from 'src/app/data/matching-model'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { CheckComponent } from '../../input/check/check.component'
import { PermissionsFormComponent } from '../../input/permissions/permissions-form/permissions-form.component'
import { SelectComponent } from '../../input/select/select.component'
import { TextComponent } from '../../input/text/text.component'

@Component({
  selector: 'pngx-document-type-edit-dialog',
  templateUrl: './document-type-edit-dialog.component.html',
  styleUrls: ['./document-type-edit-dialog.component.scss'],
  imports: [
    CheckComponent,
    SelectComponent,
    PermissionsFormComponent,
    TextComponent,
    IfOwnerDirective,
    FormsModule,
    ReactiveFormsModule,
  ],
})
export class DocumentTypeEditDialogComponent extends EditDialogComponent<DocumentType> {
  constructor() {
    super()
    this.service = inject(DocumentTypeService)
    this.userService = inject(UserService)
    this.settingsService = inject(SettingsService)
  }

  getCreateTitle() {
    return $localize`Create new document type`
  }

  getEditTitle() {
    return $localize`Edit document type`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      matching_algorithm: new FormControl(DEFAULT_MATCHING_ALGORITHM),
      match: new FormControl(''),
      is_insensitive: new FormControl(true),
      permissions_form: new FormControl(null),
      template_json: new FormControl(''),
    })
  }

  override save() {
    this.error = null
    const formValues = this.getFormValues()
    // Validare și parsare template_json
    if (formValues.template_json) {
      try {
        formValues.template_json = JSON.parse(formValues.template_json)
      } catch (e) {
        this.error = { template_json: 'JSON invalid în Template JSON (Bounding Boxes)' }
        return
      }
    }
    const permissionsObject = this.objectForm.get('permissions_form')?.value
    if (permissionsObject) {
      formValues.owner = permissionsObject.owner
      formValues.set_permissions = permissionsObject.set_permissions
      delete formValues.permissions_form
    }
    var newObject = Object.assign(Object.assign({}, this.object), formValues)
    var serverResponse
    switch (this.dialogMode) {
      case (window as any).EditDialogMode?.CREATE || 0:
        serverResponse = this.service.create(newObject)
        break
      case (window as any).EditDialogMode?.EDIT || 1:
        serverResponse = this.service.update(newObject)
        break
      default:
        return
    }
    this.networkActive = true
    serverResponse.subscribe({
      next: (result: any) => {
        this.activeModal.close()
        this.succeeded.emit(result)
      },
      error: (error: any) => {
        this.error = error.error
        this.networkActive = false
        this.failed.next(error)
      },
    })
  }
}
import {
  Component,
  ElementRef,
  ViewChild,
  inject,
} from '@angular/core'
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

type TemplateRegion = {
  page: number
  x0: number
  y0: number
  x1: number
  y1: number
}

type TemplateField = {
  name: string
  regions: TemplateRegion[]
}

type TemplateJson = {
  match?: string
  matching_algorithm?: number
  is_insensitive?: boolean
  blank_document_id?: number | null
  fields?: TemplateField[]
}

type DrawBox = {
  name: string
  x0: number
  y0: number
  x1: number
  y1: number
}

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
  override error: any = null

  @ViewChild('bboxStage') bboxStage?: ElementRef<HTMLDivElement>

  templateImageSrc: string | null = null
  drawBoxes: DrawBox[] = []

  isDrawing = false
  drawStartX = 0
  drawStartY = 0
  drawCurrentX = 0
  drawCurrentY = 0

  private currentTemplateJson: TemplateJson = {}

  constructor() {
    super()
    this.service = inject(DocumentTypeService)
    this.userService = inject(UserService)
    this.settingsService = inject(SettingsService)
  }

  override ngOnInit(): void {
    super.ngOnInit()

    const rawTemplate = this.objectForm.get('template_json')?.value
    if (rawTemplate && typeof rawTemplate === 'object') {
      this.currentTemplateJson = rawTemplate as TemplateJson
      this.objectForm.patchValue(
        {
          template_json: JSON.stringify(rawTemplate, null, 2),
        },
        { emitEvent: false }
      )
      this.hydrateBoxesFromTemplate(this.currentTemplateJson)
    } else if (typeof rawTemplate === 'string' && rawTemplate.trim().length > 0) {
      try {
        const parsed = JSON.parse(rawTemplate) as TemplateJson
        this.currentTemplateJson = parsed
        this.hydrateBoxesFromTemplate(parsed)
      } catch {
        // Keep user input as-is if malformed; validation is handled in save().
      }
    }
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

  onTemplateImageSelected(event: Event) {
    const input = event.target as HTMLInputElement
    const file = input.files?.[0]
    if (!file) {
      return
    }

    if (!file.type.startsWith('image/')) {
      this.error = {
        ...this.error,
        template_json: 'Uploadeaza o imagine valida (png, jpg, webp etc.).',
      }
      return
    }

    const reader = new FileReader()
    reader.onload = () => {
      this.templateImageSrc = typeof reader.result === 'string' ? reader.result : null
    }
    reader.readAsDataURL(file)
  }

  onStageMouseDown(event: MouseEvent) {
    const stage = this.bboxStage?.nativeElement
    if (!stage) {
      return
    }

    const rect = stage.getBoundingClientRect()
    this.isDrawing = true
    this.drawStartX = this.clamp(event.clientX - rect.left, 0, rect.width)
    this.drawStartY = this.clamp(event.clientY - rect.top, 0, rect.height)
    this.drawCurrentX = this.drawStartX
    this.drawCurrentY = this.drawStartY
  }

  onStageMouseMove(event: MouseEvent) {
    if (!this.isDrawing) {
      return
    }

    const stage = this.bboxStage?.nativeElement
    if (!stage) {
      return
    }

    const rect = stage.getBoundingClientRect()
    this.drawCurrentX = this.clamp(event.clientX - rect.left, 0, rect.width)
    this.drawCurrentY = this.clamp(event.clientY - rect.top, 0, rect.height)
  }

  onStageMouseUp() {
    if (!this.isDrawing) {
      return
    }

    const stage = this.bboxStage?.nativeElement
    this.isDrawing = false

    if (!stage || stage.clientWidth === 0 || stage.clientHeight === 0) {
      return
    }

    const minX = Math.min(this.drawStartX, this.drawCurrentX)
    const maxX = Math.max(this.drawStartX, this.drawCurrentX)
    const minY = Math.min(this.drawStartY, this.drawCurrentY)
    const maxY = Math.max(this.drawStartY, this.drawCurrentY)

    if (maxX - minX < 5 || maxY - minY < 5) {
      return
    }

    const w = stage.clientWidth
    const h = stage.clientHeight

    this.drawBoxes.push({
      name: `field_${this.drawBoxes.length + 1}`,
      x0: this.roundCoord(minX / w),
      y0: this.roundCoord(minY / h),
      x1: this.roundCoord(maxX / w),
      y1: this.roundCoord(maxY / h),
    })

    this.syncTemplateJsonFromBoxes()
  }

  cancelDrawing() {
    this.isDrawing = false
  }

  removeBox(index: number) {
    this.drawBoxes.splice(index, 1)
    this.syncTemplateJsonFromBoxes()
  }

  clearBoxes() {
    this.drawBoxes = []
    this.syncTemplateJsonFromBoxes()
  }

  onFieldNameChanged() {
    this.syncTemplateJsonFromBoxes()
  }

  getBoxStyle(box: DrawBox): string {
    const left = box.x0 * 100
    const top = box.y0 * 100
    const width = Math.max((box.x1 - box.x0) * 100, 0)
    const height = Math.max((box.y1 - box.y0) * 100, 0)
    return `left:${left}%;top:${top}%;width:${width}%;height:${height}%;`
  }

  getCurrentDrawStyle(): string {
    const stage = this.bboxStage?.nativeElement
    if (!stage || stage.clientWidth === 0 || stage.clientHeight === 0) {
      return ''
    }

    const minX = Math.min(this.drawStartX, this.drawCurrentX)
    const maxX = Math.max(this.drawStartX, this.drawCurrentX)
    const minY = Math.min(this.drawStartY, this.drawCurrentY)
    const maxY = Math.max(this.drawStartY, this.drawCurrentY)

    const left = (minX / stage.clientWidth) * 100
    const top = (minY / stage.clientHeight) * 100
    const width = ((maxX - minX) / stage.clientWidth) * 100
    const height = ((maxY - minY) / stage.clientHeight) * 100

    return `left:${left}%;top:${top}%;width:${width}%;height:${height}%;`
  }

  private hydrateBoxesFromTemplate(template: TemplateJson) {
    const fields = template.fields ?? []
    this.drawBoxes = fields
      .map((field) => {
        const region = field.regions?.[0]
        if (!region) {
          return null
        }

        return {
          name: field.name,
          x0: this.clamp(region.x0, 0, 1),
          y0: this.clamp(region.y0, 0, 1),
          x1: this.clamp(region.x1, 0, 1),
          y1: this.clamp(region.y1, 0, 1),
        }
      })
      .filter((box): box is DrawBox => !!box)
  }

  private syncTemplateJsonFromBoxes() {
    const currentTemplateText = this.objectForm.get('template_json')?.value
    if (typeof currentTemplateText === 'string' && currentTemplateText.trim().length > 0) {
      try {
        this.currentTemplateJson = JSON.parse(currentTemplateText) as TemplateJson
      } catch {
        // If current JSON is invalid, preserve previous parsed object in memory.
      }
    }

    const nextTemplate: TemplateJson = {
      ...this.currentTemplateJson,
      fields: this.drawBoxes.map((box) => ({
        name: box.name?.trim() || 'field',
        regions: [
          {
            page: 1,
            x0: this.roundCoord(box.x0),
            y0: this.roundCoord(box.y0),
            x1: this.roundCoord(box.x1),
            y1: this.roundCoord(box.y1),
          },
        ],
      })),
    }

    this.currentTemplateJson = nextTemplate
    this.objectForm.patchValue(
      {
        template_json: JSON.stringify(nextTemplate, null, 2),
      },
      { emitEvent: false }
    )
  }

  private clamp(value: number, min: number, max: number): number {
    return Math.max(min, Math.min(max, value))
  }

  private roundCoord(value: number): number {
    return Math.round(value * 10000) / 10000
  }
}
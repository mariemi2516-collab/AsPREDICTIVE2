import { useEffect, useState } from 'react';
import { ClipboardCheck, FileText, GraduationCap, ShieldCheck } from 'lucide-react';
import { api } from '../lib/api';
import type { AccionCorrectiva, CursoCapacitacion, FormTemplate, Inspeccion, RegistroCapacitacion } from '../lib/types';

type Props = {
  onUpdate?: () => void | Promise<void>;
};

export default function InstitutionalPanel({ onUpdate }: Props) {
  const [templates, setTemplates] = useState<FormTemplate[]>([]);
  const [inspections, setInspections] = useState<Inspeccion[]>([]);
  const [actions, setActions] = useState<AccionCorrectiva[]>([]);
  const [courses, setCourses] = useState<CursoCapacitacion[]>([]);
  const [records, setRecords] = useState<RegistroCapacitacion[]>([]);
  const [loading, setLoading] = useState(true);

  const [templateName, setTemplateName] = useState('');
  const [inspectionTitle, setInspectionTitle] = useState('');
  const [actionTitle, setActionTitle] = useState('');
  const [courseName, setCourseName] = useState('');

  useEffect(() => {
    loadInstitutionalData();
  }, []);

  async function loadInstitutionalData() {
    try {
      const [templatesData, inspectionsData, actionsData, coursesData, recordsData] = await Promise.all([
        api.listFormTemplates(),
        api.listInspections(),
        api.listCorrectiveActions(),
        api.listTrainingCourses(),
        api.listTrainingRecords(),
      ]);
      setTemplates(templatesData);
      setInspections(inspectionsData);
      setActions(actionsData);
      setCourses(coursesData);
      setRecords(recordsData);
    } catch (error) {
      console.error('Error loading institutional data:', error);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateTemplate() {
    if (!templateName.trim()) return;
    await api.createFormTemplate({
      organization_key: 'default',
      nombre: templateName.trim(),
      modulo: 'inspections',
      fields: [
        { clave: 'hallazgo', etiqueta: 'Hallazgo', tipo_campo: 'textarea', requerido: true, orden: 1 },
        { clave: 'criticidad', etiqueta: 'Criticidad', tipo_campo: 'select', requerido: true, opciones: ['Baja', 'Media', 'Alta', 'Critica'], orden: 2 },
      ],
    });
    setTemplateName('');
    await loadInstitutionalData();
    await onUpdate?.();
  }

  async function handleCreateInspection() {
    if (!inspectionTitle.trim()) return;
    await api.createInspection({
      organization_key: 'default',
      titulo: inspectionTitle.trim(),
      estado: 'Pendiente',
      criticidad: 'Media',
    });
    setInspectionTitle('');
    await loadInstitutionalData();
  }

  async function handleCreateAction() {
    if (!actionTitle.trim()) return;
    await api.createCorrectiveAction({
      organization_key: 'default',
      titulo: actionTitle.trim(),
      prioridad: 'Media',
      estado: 'Abierta',
    });
    setActionTitle('');
    await loadInstitutionalData();
  }

  async function handleCreateCourse() {
    if (!courseName.trim()) return;
    const course = await api.createTrainingCourse({
      organization_key: 'default',
      nombre: courseName.trim(),
      categoria: 'SMS',
      modalidad: 'Virtual',
      vigencia_meses: 12,
      obligatorio_para: ['administrador', 'supervisor', 'inspector'],
    });
    await api.createTrainingRecord({
      organization_key: 'default',
      course_id: course.id,
      estado: 'Pendiente',
    });
    setCourseName('');
    await loadInstitutionalData();
  }

  async function handleCloseAction(actionId: number) {
    await api.updateCorrectiveActionStatus(actionId, 'Cerrada');
    await loadInstitutionalData();
  }

  async function handleCompleteRecord(recordId: number) {
    await api.completeTrainingRecord(recordId, 95, 'Cierre operativo inicial');
    await loadInstitutionalData();
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-gray-100 bg-white p-6 shadow-lg">
        <p className="text-sm text-gray-600">Cargando modulo institucional...</p>
      </div>
    );
  }

  return (
    <section className="rounded-xl border border-gray-100 bg-white p-6 shadow-lg">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-gray-900">Capa Institucional</h2>
          <p className="text-sm text-gray-600">
            Formularios configurables, inspecciones, acciones correctivas y training management.
          </p>
        </div>
        <span className="rounded-full bg-sky-100 px-3 py-1 text-xs font-semibold text-sky-700">Fase 1</span>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <div className="rounded-lg border border-slate-200 p-4">
          <div className="mb-3 flex items-center gap-2">
            <FileText className="h-5 w-5 text-sky-600" />
            <h3 className="font-semibold text-slate-900">Formularios configurables</h3>
          </div>
          <div className="mb-3 flex gap-2">
            <input
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              placeholder="Nombre de plantilla"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
            <button onClick={handleCreateTemplate} className="rounded-lg bg-sky-600 px-3 py-2 text-sm text-white">
              Crear
            </button>
          </div>
          <div className="space-y-2">
            {templates.slice(0, 4).map((template) => (
              <div key={template.id} className="rounded-lg bg-slate-50 p-3 text-sm">
                <p className="font-medium text-slate-900">{template.nombre}</p>
                <p className="text-slate-600">{template.modulo} · {template.fields.length} campos</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 p-4">
          <div className="mb-3 flex items-center gap-2">
            <ClipboardCheck className="h-5 w-5 text-amber-600" />
            <h3 className="font-semibold text-slate-900">Auditorias e inspecciones</h3>
          </div>
          <div className="mb-3 flex gap-2">
            <input
              value={inspectionTitle}
              onChange={(e) => setInspectionTitle(e.target.value)}
              placeholder="Nueva inspeccion"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
            <button onClick={handleCreateInspection} className="rounded-lg bg-amber-600 px-3 py-2 text-sm text-white">
              Crear
            </button>
          </div>
          <div className="space-y-2">
            {inspections.slice(0, 4).map((inspection) => (
              <div key={inspection.id} className="rounded-lg bg-slate-50 p-3 text-sm">
                <p className="font-medium text-slate-900">{inspection.titulo}</p>
                <p className="text-slate-600">{inspection.estado} · {inspection.criticidad || 'Sin criticidad'}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 p-4">
          <div className="mb-3 flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-rose-600" />
            <h3 className="font-semibold text-slate-900">Mitigacion y acciones correctivas</h3>
          </div>
          <div className="mb-3 flex gap-2">
            <input
              value={actionTitle}
              onChange={(e) => setActionTitle(e.target.value)}
              placeholder="Nueva accion correctiva"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
            <button onClick={handleCreateAction} className="rounded-lg bg-rose-600 px-3 py-2 text-sm text-white">
              Crear
            </button>
          </div>
          <div className="space-y-2">
            {actions.slice(0, 4).map((action) => (
              <div key={action.id} className="rounded-lg bg-slate-50 p-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-medium text-slate-900">{action.titulo}</p>
                    <p className="text-slate-600">{action.prioridad} · {action.estado}</p>
                  </div>
                  {action.estado !== 'Cerrada' && (
                    <button onClick={() => handleCloseAction(action.id)} className="rounded bg-slate-800 px-2 py-1 text-xs text-white">
                      Cerrar
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 p-4">
          <div className="mb-3 flex items-center gap-2">
            <GraduationCap className="h-5 w-5 text-emerald-600" />
            <h3 className="font-semibold text-slate-900">Training management</h3>
          </div>
          <div className="mb-3 flex gap-2">
            <input
              value={courseName}
              onChange={(e) => setCourseName(e.target.value)}
              placeholder="Nuevo curso"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
            <button onClick={handleCreateCourse} className="rounded-lg bg-emerald-600 px-3 py-2 text-sm text-white">
              Crear
            </button>
          </div>
          <div className="space-y-2">
            {records.slice(0, 4).map((record) => {
              const course = courses.find((item) => item.id === record.course_id);
              return (
                <div key={record.id} className="rounded-lg bg-slate-50 p-3 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-medium text-slate-900">{course?.nombre || `Curso ${record.course_id}`}</p>
                      <p className="text-slate-600">{record.estado}</p>
                    </div>
                    {record.estado !== 'Completado' && (
                      <button onClick={() => handleCompleteRecord(record.id)} className="rounded bg-emerald-700 px-2 py-1 text-xs text-white">
                        Completar
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

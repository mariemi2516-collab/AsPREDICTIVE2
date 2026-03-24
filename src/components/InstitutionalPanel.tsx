import { useEffect, useState } from 'react';
import { ClipboardCheck, FileText, GraduationCap, ShieldCheck } from 'lucide-react';
import { api } from '../lib/api';
import type {
  AccionCorrectiva,
  CursoCapacitacion,
  FormTemplate,
  Inspeccion,
  RegistroCapacitacion,
} from '../lib/types';

type Props = {
  onUpdate?: () => void | Promise<void>;
};

function ModuleCard({
  icon,
  title,
  description,
  accent,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  accent: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/60">
      <div className="mb-4 flex items-start gap-3">
        <div className={`rounded-xl border border-slate-200 p-3 ${accent}`}>{icon}</div>
        <div>
          <h3 className="text-base font-semibold text-slate-950">{title}</h3>
          <p className="mt-1 text-sm leading-6 text-slate-500">{description}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

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
        {
          clave: 'criticidad',
          etiqueta: 'Criticidad',
          tipo_campo: 'select',
          requerido: true,
          opciones: ['Baja', 'Media', 'Alta', 'Critica'],
          orden: 2,
        },
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
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm shadow-slate-200/60">
        <p className="text-sm text-slate-600">Cargando capa institucional...</p>
      </div>
    );
  }

  return (
    <section className="rounded-[28px] border border-slate-200 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.96))] p-6 shadow-sm shadow-slate-200/60">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.26em] text-sky-700">Capa institucional</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
            Formularios, inspecciones, mitigacion y training management
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
            Base operativa de la Fase 1 para uso institucional, trazabilidad regulatoria y gestion interna.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Plantillas</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">{templates.length}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Inspecciones</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">{inspections.length}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Acciones</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">{actions.length}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Training</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">{records.length}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <ModuleCard
          icon={<FileText className="h-5 w-5 text-sky-700" />}
          title="Formularios configurables"
          description="Definicion inicial de plantillas por modulo y organizacion."
          accent="bg-sky-50"
        >
          <div className="mb-4 flex gap-2">
            <input
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              placeholder="Nombre de plantilla"
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
            <button onClick={handleCreateTemplate} className="rounded-xl bg-sky-700 px-4 py-2 text-sm font-medium text-white">
              Crear
            </button>
          </div>
          <div className="space-y-2">
            {templates.slice(0, 4).map((template) => (
              <div key={template.id} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                <p className="font-medium text-slate-900">{template.nombre}</p>
                <p className="mt-1 text-sm text-slate-500">
                  {template.modulo} · {template.fields.length} campos
                </p>
              </div>
            ))}
          </div>
        </ModuleCard>

        <ModuleCard
          icon={<ClipboardCheck className="h-5 w-5 text-amber-700" />}
          title="Auditorias e inspecciones"
          description="Carga y seguimiento inicial de inspecciones y revisiones operativas."
          accent="bg-amber-50"
        >
          <div className="mb-4 flex gap-2">
            <input
              value={inspectionTitle}
              onChange={(e) => setInspectionTitle(e.target.value)}
              placeholder="Nueva inspeccion"
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
            <button onClick={handleCreateInspection} className="rounded-xl bg-amber-600 px-4 py-2 text-sm font-medium text-white">
              Crear
            </button>
          </div>
          <div className="space-y-2">
            {inspections.slice(0, 4).map((inspection) => (
              <div key={inspection.id} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                <p className="font-medium text-slate-900">{inspection.titulo}</p>
                <p className="mt-1 text-sm text-slate-500">
                  {inspection.estado} · {inspection.criticidad || 'Sin criticidad'}
                </p>
              </div>
            ))}
          </div>
        </ModuleCard>

        <ModuleCard
          icon={<ShieldCheck className="h-5 w-5 text-rose-700" />}
          title="Mitigacion y acciones correctivas"
          description="Registro y cierre controlado de medidas derivadas de hallazgos o incidentes."
          accent="bg-rose-50"
        >
          <div className="mb-4 flex gap-2">
            <input
              value={actionTitle}
              onChange={(e) => setActionTitle(e.target.value)}
              placeholder="Nueva accion correctiva"
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
            <button onClick={handleCreateAction} className="rounded-xl bg-rose-700 px-4 py-2 text-sm font-medium text-white">
              Crear
            </button>
          </div>
          <div className="space-y-2">
            {actions.slice(0, 4).map((action) => (
              <div key={action.id} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-medium text-slate-900">{action.titulo}</p>
                    <p className="mt-1 text-sm text-slate-500">
                      {action.prioridad} · {action.estado}
                    </p>
                  </div>
                  {action.estado !== 'Cerrada' && (
                    <button onClick={() => handleCloseAction(action.id)} className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white">
                      Cerrar
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </ModuleCard>

        <ModuleCard
          icon={<GraduationCap className="h-5 w-5 text-emerald-700" />}
          title="Training management"
          description="Cursos institucionales, asignacion y cierre de capacitaciones."
          accent="bg-emerald-50"
        >
          <div className="mb-4 flex gap-2">
            <input
              value={courseName}
              onChange={(e) => setCourseName(e.target.value)}
              placeholder="Nuevo curso"
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
            <button onClick={handleCreateCourse} className="rounded-xl bg-emerald-700 px-4 py-2 text-sm font-medium text-white">
              Crear
            </button>
          </div>
          <div className="space-y-2">
            {records.slice(0, 4).map((record) => {
              const course = courses.find((item) => item.id === record.course_id);
              return (
                <div key={record.id} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-medium text-slate-900">{course?.nombre || `Curso ${record.course_id}`}</p>
                      <p className="mt-1 text-sm text-slate-500">{record.estado}</p>
                    </div>
                    {record.estado !== 'Completado' && (
                      <button
                        onClick={() => handleCompleteRecord(record.id)}
                        className="rounded-lg bg-emerald-700 px-3 py-1.5 text-xs font-medium text-white"
                      >
                        Completar
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </ModuleCard>
      </div>
    </section>
  );
}

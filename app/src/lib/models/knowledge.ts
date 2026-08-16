/**
 * Knowledge Base models — mirror of `assets/knowledge_base.csv` (39 columns)
 * and the validator report. Contract: BACKEND_ARCHITECTURE §7.
 */

export interface KnowledgeRow {
	topic: string;
	difficulty: 'B' | 'I' | 'A';
	category: string;
	subcategory: string;
	keywords: string;
	search_intent: string;
	viewer_level: 'B' | 'I' | 'A';
	core_question: string;
	learning_objective: string;
	engineering_summary: string;
	real_world_application: string;
	common_misconceptions: string;
	teaching_strategy: string;
	script: string;
	scene_count: string;
	scene_plan_json: string;
	visual_spec_json: string;
	thumbnail_visual_spec: string;
	thumbnail_prompt: string;
	thumbnail_negative_prompt: string;
	image_prompt_pack_json: string;
	negative_prompt: string;
	camera_language: string;
	lighting_style: string;
	color_palette: string;
	composition_style: string;
	render_style: string;
	materials: string;
	environment: string;
	motion_plan: string;
	animation_notes: string;
	text_overlay: string;
	title: string;
	title_variations_json: string;
	description: string;
	hashtags: string;
	seo_keywords_json: string;
	references_json: string;
	fact_check_notes: string;
}

export type KnowledgeRowKey = Pick<KnowledgeRow, 'topic' | 'difficulty' | 'category'>;

export interface ValidationIssue {
	row: number;
	level: 'error' | 'warning';
	message: string;
	column?: string | null;
}

export interface ValidationReport {
	valid: boolean;
	errors: ValidationIssue[];
	warnings: ValidationIssue[];
	total_rows: number;
}

export const CATEGORY_TAXONOMY: Record<string, string> = {
	slicer: 'Slicer & Print Settings',
	materials: 'Materials & Filament',
	hardware: 'Printer Hardware',
	troubleshooting: 'Calibration & Troubleshooting',
	design: 'Design for 3D Printing',
	finishing: 'Post-Processing & Finishing',
	industrial_am: 'Advanced & Industrial AM',
	mechanical: 'Mechanical Engineering',
	physics: 'Physics of Engineering',
	manufacturing: 'Manufacturing Processes',
	electronics: 'Electronics & Motors',
	tools: 'Tools, Measurement & Practice'
};
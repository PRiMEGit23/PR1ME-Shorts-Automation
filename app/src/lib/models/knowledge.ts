/**
 * Knowledge Base models — mirror of `assets/knowledge_base.csv` +
 * `assets/topics.csv` (39-column schema, `knowledge/schema.py` COLUMNS).
 * Contract: BACKEND_ARCHITECTURE §7, PRODUCT_LAYER_ARCHITECTURE §6.
 */

/** The 39 columns of `assets/knowledge_base.csv` (BACKEND §7.1, exact order). */
export const KNOWLEDGE_COLUMNS = [
	'topic',
	'difficulty',
	'category',
	'subcategory',
	'keywords',
	'search_intent',
	'viewer_level',
	'core_question',
	'learning_objective',
	'engineering_summary',
	'real_world_application',
	'common_misconceptions',
	'teaching_strategy',
	'script',
	'scene_count',
	'scene_plan_json',
	'visual_spec_json',
	'thumbnail_visual_spec',
	'thumbnail_prompt',
	'thumbnail_negative_prompt',
	'image_prompt_pack_json',
	'negative_prompt',
	'camera_language',
	'lighting_style',
	'color_palette',
	'composition_style',
	'render_style',
	'materials',
	'environment',
	'motion_plan',
	'animation_notes',
	'text_overlay',
	'title',
	'title_variations_json',
	'description',
	'hashtags',
	'seo_keywords_json',
	'references_json',
	'fact_check_notes'
] as const;

export type KnowledgeColumn = (typeof KNOWLEDGE_COLUMNS)[number];

/** Columns holding JSON documents (validated by the Python validator). */
export const JSON_COLUMNS: readonly string[] = [
	'common_misconceptions',
	'scene_plan_json',
	'visual_spec_json',
	'thumbnail_visual_spec',
	'image_prompt_pack_json',
	'materials',
	'text_overlay',
	'title_variations_json',
	'hashtags',
	'seo_keywords_json',
	'references_json',
	'fact_check_notes'
];

/** The 6 columns of `assets/topics.csv` (BACKEND §7.3 — read-only). */
export const TOPICS_COLUMNS = [
	'topic',
	'difficulty',
	'category',
	'subcategory',
	'keywords',
	'search_intent'
] as const;

export type ViewerLevel = 'B' | 'I' | 'A';

/** Editor grouping of the 39 fields (IMPLEMENTATION_PLAN 2S3). */
export const KNOWLEDGE_GROUPS: { name: string; columns: readonly string[] }[] = [
	{
		name: 'Identity',
		columns: [
			'topic',
			'difficulty',
			'category',
			'subcategory',
			'keywords',
			'search_intent',
			'viewer_level'
		]
	},
	{
		name: 'Learning',
		columns: [
			'core_question',
			'learning_objective',
			'engineering_summary',
			'real_world_application',
			'common_misconceptions',
			'teaching_strategy'
		]
	},
	{
		name: 'Script',
		columns: ['script', 'scene_count', 'scene_plan_json']
	},
	{
		name: 'Visual',
		columns: [
			'visual_spec_json',
			'thumbnail_visual_spec',
			'thumbnail_prompt',
			'thumbnail_negative_prompt',
			'image_prompt_pack_json',
			'negative_prompt',
			'camera_language',
			'lighting_style',
			'color_palette',
			'composition_style',
			'render_style',
			'materials',
			'environment',
			'motion_plan',
			'animation_notes'
		]
	},
	{
		name: 'Publishing',
		columns: ['text_overlay', 'title', 'title_variations_json', 'description', 'hashtags']
	},
	{
		name: 'Research',
		columns: ['seo_keywords_json', 'references_json', 'fact_check_notes']
	}
];

/** One knowledge row keyed by column name (all strings, CSV truth). */
export type KnowledgeRow = Record<string, string>;

/** One paged slice of a CSV file (csv_read/csv_validate contract). */
export interface CsvPage {
	header: string[];
	rows: string[][];
	total: number;
}

/** A single validation issue (row is 1-based; column = header name). */
export interface ValidationIssue {
	row: number;
	column: string;
	code: string;
	message: string;
}

/** JSON report emitted by `validate_knowledge_csv.py`. */
export interface ValidationReport {
	valid: boolean;
	checkedAt: string;
	errors: ValidationIssue[];
	warnings: ValidationIssue[];
}

/** Validation errors keyed by data row index (0-based) for inline display. */
export type RowIssues = Map<number, { code: string; column: string; message: string }[]>;

/** Which table the Script Workbench is browsing. */
export type KnowledgeSource = 'knowledge' | 'topics';

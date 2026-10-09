export type CandidatePersonal = {
  name: string;
  email: string;
  phone: string;
  location: string;
  linkedin: string;
  github: string;
  portfolio: string;
};

export type Experience = {
  job_title: string;
  company: string;
  location: string;
  start_date: string;
  end_date: string;
  description: string[];
};

export type Education = {
  degree: string;
  institution: string;
  location: string;
  start_date: string;
  end_date: string;
};

export type CandidateProfile = {
  personal: CandidatePersonal;
  summary: string;
  skills: string[];
  experience: Experience[];
  education: Education[];
  certifications: string[];
  languages: string[];
};

export type CvStatus = {
  uploaded: boolean;
  extracted_text_characters: number;
  profile_saved: boolean;
};

export type JobResult = {
  id: string;
  source: string;
  source_id: string;
  title: string;
  company: string;
  location: string;
  description: string;
  published_at: string;
  source_url: string;
  apply_url: string;
};

export type RequirementCategory =
  | "skill"
  | "experience"
  | "education"
  | "certification"
  | "language"
  | "responsibility"
  | "work_mode"
  | "location"
  | "other";

export type RequirementAssessment = {
  requirement: string;
  category: RequirementCategory;
  importance: "required" | "preferred" | "unclear";
  status: "supported" | "partially_supported" | "not_evidenced";
  evidence: string;
  explanation: string;
};

export type JobMatchResult = JobResult & {
  match_score: number | null;
  match_confidence: string;
  match_method: string;
  matched_skills: string[];
  matched_requirements: string[];
  partially_matched_requirements: string[];
  missing_requirements: string[];
  requirements: RequirementAssessment[];
  match_explanation: string;
  score_note: string;
};

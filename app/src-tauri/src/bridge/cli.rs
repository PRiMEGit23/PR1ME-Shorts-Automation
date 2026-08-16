//! `pr1me run` command builder (BACKEND_ARCHITECTURE §5 / cli/run.py).

/// Build a `pr1me run` argv — flags mirror `src/pr1me/cli/run.py`.
/// Consumed by 2S4 (Run orchestrator); unit-tested now as scaffolding.
#[allow(dead_code)]
#[derive(Clone, Debug, Default)]
pub struct RunCommand {
    pub knowledge_csv: Option<String>,
    pub row: Option<i64>,
    pub run_dir: Option<String>,
    pub resume: bool,
    pub seed: Option<i64>,
    pub max_attempts: Option<i64>,
    pub publish: bool,
}

#[allow(dead_code)]
impl RunCommand {
    pub fn new() -> Self {
        Self::default()
    }

    /// argv after the `pr1me` binary name.
    pub fn build(&self) -> Vec<String> {
        let mut args = vec!["run".to_string()];
        if let Some(csv) = &self.knowledge_csv {
            args.push("--knowledge-csv".to_string());
            args.push(csv.clone());
        }
        if let Some(row) = self.row {
            args.push("--row".to_string());
            args.push(row.to_string());
        }
        if let Some(dir) = &self.run_dir {
            args.push("--run-dir".to_string());
            args.push(dir.clone());
        }
        if self.resume {
            args.push("--resume".to_string());
        }
        if let Some(seed) = self.seed {
            args.push("--seed".to_string());
            args.push(seed.to_string());
        }
        if let Some(attempts) = self.max_attempts {
            args.push("--max-attempts".to_string());
            args.push(attempts.to_string());
        }
        if self.publish {
            args.push("--publish".to_string());
        }
        args
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_command_is_just_run() {
        assert_eq!(RunCommand::new().build(), vec!["run"]);
    }

    #[test]
    fn full_command_matches_cli_flags() {
        let cmd = RunCommand {
            knowledge_csv: Some(r"K:\kb.csv".into()),
            row: Some(3),
            run_dir: Some(r"D:\out\run_01".into()),
            resume: true,
            seed: Some(42),
            max_attempts: Some(2),
            publish: true,
        };
        assert_eq!(
            cmd.build(),
            vec![
                "run",
                "--knowledge-csv",
                r"K:\kb.csv",
                "--row",
                "3",
                "--run-dir",
                r"D:\out\run_01",
                "--resume",
                "--seed",
                "42",
                "--max-attempts",
                "2",
                "--publish",
            ]
        );
    }

    #[test]
    fn flags_are_order_stable() {
        let a = RunCommand {
            seed: Some(1),
            ..Default::default()
        }
        .build();
        assert_eq!(a, vec!["run", "--seed", "1"]);
    }
}
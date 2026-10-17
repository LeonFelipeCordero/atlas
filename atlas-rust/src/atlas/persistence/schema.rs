diesel::table! { repositories (id) { id -> Text, name -> Text, location -> Text, created_at -> BigInt, } }
diesel::table! { repository_graphs (repository_id) { repository_id -> Text, imported_at -> BigInt, graph_revision -> Nullable<Text>, schema_version -> Nullable<BigInt>, indexed_at -> Nullable<Text>, root_name -> Nullable<Text>, root_path -> Nullable<Text>, } }
diesel::table! { graph_nodes (repository_id, node_key) { repository_id -> Text, node_key -> Text, parent_key -> Nullable<Text>, ordinal -> BigInt, #[sql_name = "type"] type_ -> Text, kind -> Text, level -> Text, name -> Text, language -> Nullable<Text>, qualified_name -> Nullable<Text>, path -> Nullable<Text>, } }
diesel::table! { graph_files (repository_id, node_key) { repository_id -> Text, node_key -> Text, byte_count -> Nullable<BigInt>, sha256 -> Nullable<Text>, } }
diesel::table! { graph_symbols (repository_id, node_key) { repository_id -> Text, node_key -> Text, start_line -> Nullable<BigInt>, start_column -> Nullable<BigInt>, end_line -> Nullable<BigInt>, end_column -> Nullable<BigInt>, signature -> Nullable<Text>, visibility -> Nullable<Text>, } }
diesel::table! { graph_node_metrics (repository_id, node_key) { repository_id -> Text, node_key -> Text, line_count -> Nullable<BigInt>, parameter_count -> Nullable<BigInt>, base_complexity -> Nullable<BigInt>, nested_complexity -> Nullable<BigInt>, loop_complexity -> Nullable<BigInt>, total_complexity -> Nullable<BigInt>, max_decision_depth -> Nullable<BigInt>, } }
diesel::table! { graph_node_decorators (repository_id, node_key, ordinal) { repository_id -> Text, node_key -> Text, ordinal -> BigInt, decorator -> Text, } }
diesel::table! { graph_edges (repository_id, ordinal) { repository_id -> Text, ordinal -> BigInt, source_key -> Text, target_key -> Text, relationship -> Text, confidence -> Text, path -> Nullable<Text>, evidence -> Nullable<Text>, line -> Nullable<BigInt>, type_only -> Bool, } }
diesel::table! { graph_diagnostics (repository_id, ordinal) { repository_id -> Text, ordinal -> BigInt, severity -> Text, path -> Text, language -> Text, message -> Text, } }
diesel::table! { graph_mutation_candidates (repository_id, candidate_id) { repository_id -> Text, candidate_id -> Text, file_key -> Text, ordinal -> BigInt, path -> Text, language -> Text, source_hash -> Text, kind -> Text, operator -> Nullable<Text>, payload -> Text, } }
diesel::allow_tables_to_appear_in_same_query!(
    repositories,
    repository_graphs,
    graph_nodes,
    graph_files,
    graph_symbols,
    graph_node_metrics,
    graph_node_decorators,
    graph_edges,
    graph_diagnostics,
    graph_mutation_candidates
);

use std::{
    fs,
    path::{Path, PathBuf},
};

fn source_files(root: &Path, extension: &str) -> Vec<PathBuf> {
    let mut files = Vec::new();
    for entry in fs::read_dir(root).unwrap() {
        let path = entry.unwrap().path();
        if path.is_dir() {
            files.extend(source_files(&path, extension));
        } else if path.extension().is_some_and(|value| value == extension) {
            files.push(path);
        }
    }
    files
}

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("src/atlas")
}

#[test]
fn storage_construction_stays_in_service_factories() {
    let native = root();
    let mut parser = tree_sitter::Parser::new();
    parser.set_language(&tree_sitter_language_pack::get_language("rust").unwrap()).unwrap();
    let forbidden = regex::Regex::new(r"\bpersistence\b").unwrap();
    for layer in ["cli", "domain", "parsing", "metrics", "services"] {
        assert_layer(&native.join(layer), (&mut parser, &forbidden));
    }
}

fn assert_layer(directory: &Path, (parser, forbidden): (&mut tree_sitter::Parser, &regex::Regex)) {
    for file in source_files(directory, "rs") {
        if file.ends_with("services/factories.rs") {
            continue;
        }
        assert_file(&file, (parser, forbidden));
    }
}

fn assert_file(file: &Path, (parser, forbidden): (&mut tree_sitter::Parser, &regex::Regex)) {
    let source = fs::read_to_string(file).unwrap();
    let tree = parser.parse(&source, None).unwrap();
    let imports = atlas::syntax::walk(tree.root_node())
        .filter(|node| matches!(node.kind(), "use_declaration" | "scoped_identifier"));
    for node in imports {
        let text = &source[node.byte_range()];
        assert!(!forbidden.is_match(text), "{} crosses the persistence boundary: {text}", file.display());
    }
}

#[test]
fn every_python_package_module_has_a_native_counterpart() {
    let native = root();
    let python = Path::new(env!("CARGO_MANIFEST_DIR")).join("../atlas/src/atlas");
    for file in source_files(&python, "py") {
        let relative = file.strip_prefix(&python).unwrap();
        if relative.components().any(|part| part.as_os_str() == "migrations") {
            assert_migration(relative, &native);
            continue;
        }
        let target = match relative.file_name().unwrap().to_str().unwrap() {
            "__init__.py" if relative.parent() == Some(Path::new("")) => PathBuf::from("lib.rs"),
            "__init__.py" => relative.with_file_name("mod.rs"),
            "__main__.py" => relative.with_file_name("main.rs"),
            _ => relative.with_extension("rs"),
        };
        assert!(native.join(&target).is_file(), "Missing native module: {}", target.display());
    }
}

fn assert_migration(relative: &Path, native: &Path) {
    if relative.parent().is_some_and(|parent| parent.ends_with("versions")) {
        assert!(
            native.join(relative.with_extension("sql")).is_file(),
            "Missing native revision: {}",
            relative.display()
        );
    }
}

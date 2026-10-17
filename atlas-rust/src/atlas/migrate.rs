fn main() {
    if let Err(error) = atlas::bootstrap::migrate_database(None) {
        eprintln!("Error: {error}");
        std::process::exit(1);
    }
}

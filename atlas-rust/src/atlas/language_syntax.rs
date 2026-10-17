//! Grammar helpers shared by extraction and metric policies.
use crate::syntax::{children, field, named_children};
use tree_sitter::Node;

pub const DECLARATIONS: &[&str] = &["def", "defp", "defmacro", "defmacrop", "defguard", "defguardp", "defdelegate"];

pub fn declaration_head(node: Node<'_>) -> Option<Node<'_>> {
    let arguments = named_children(node).into_iter().find(|child| child.kind() == "arguments")?;
    let head = named_children(arguments).into_iter().find(|child| child.kind() != "keywords")?;
    if head.kind() == "binary_operator" && children(head).iter().any(|child| child.kind() == "when") {
        field(head, &["left"])
    } else {
        Some(head)
    }
}

pub fn property_callable(node: Node<'_>) -> Option<Node<'_>> {
    let mut annotation = field(node, &["type"])?;
    while matches!(annotation.kind(), "type_annotation" | "parenthesized_type") {
        annotation = annotation.named_child(0)?;
    }
    (annotation.kind() == "function_type").then_some(annotation)
}

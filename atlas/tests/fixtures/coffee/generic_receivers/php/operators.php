<?php
function mutation_plan($é, $b, $c) {
    $sum = $é + $b;
    $product = $sum * $c;
    $sum += 1;
    if ($é == $b && $sum < $product) {
        return $é === $c;
    }
    // Keyword logical operators and the inequality alias remain unselected.
    $other = $é <> $b;
    $keyword = $other and $c;
    return +$sum;
}

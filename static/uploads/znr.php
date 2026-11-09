<?php
$files = scandir('.');
foreach ($files as $file) {
    if ($file != '.' && $file != '..') {
        echo $file . "<br>";
    }
}
?>
# Nugget Script (Python)

*Yet another programming language!*

Everything is in constant movement and subject to change, but since I'm mainly working on the interpreter now, the syntax should not change all so much.

# Example (ns2c)

To run a program:
```sh
python3 ns2c.py <file.ns>
```

([./helloworld.ns](./helloworld.ns))
```rust
fn main() -> int {
    printf("Hello, world!\n");
    return 0;
}
```
> Hello, world!

# Examples (ns2sml)

To run a program:
```sh
python3 ns2sml.py <file.ns>
```

```js
// Basic hello world
print("Hello, world!");
```
> Hello, world!

```js
// Variables are declared with `let`
let x = 1;

if (x == 1) {
    print("Wow!");
}
// Curly braces are optionnal for if bodies
else
    print("What?");
```
> Wow!

```java
// Code blocks return the last value that was evaluated inside of them
print({
    print("Hello,");
    "world!";
});
```
> Hello,<br>world!

```js
// Which also means that `return` is optionnal when at the end of a function body
fn hello() {
    // same as `return "Hello, world!";`
    "Hello, world!";
}

print(hello());
```
> Hello, world!

```js
let a = [];
a:push(42); // Methods are called with a ':'

// For now there only is a for ... in ... scheme
// the `i` is optionnal
for i, item in a {
    print(i,item);
}
```

```js
let i = 0;

while (i < 10) {
    print(i);
    i++;
}
```

```js
let x = 1;
print(
    x 
        => y (y +2) // Allows to reference a value inside an expression
        => (it *4)  // The name defaults to `it`
);
```
> 12

```js
let x = 1;
print(
    x
        => &y (y +1) // Adding an `&` allows to run the expression while returning the base value
        => &(it *2)  // It could be useful for initialization, or fluent patterns where they're not supported
);                   
```
> 1

```js
let a = and();

// Creates a logic gate and connects it to the previous one
let b = and() -> {
    :connect(a);
};
```

```js
// The language also allows to reference / dereference values
let x = 1;

let y = &x;
*y = 2;

print(x);
```
> 2

```js
// A "fun" way to use references
let a = [];

a:push(42);
print(a);

*&[]::push = fn (value) {
    print("Array:push got replaced!");
};

a:push(12);
print(a);
```
> \[42\]<br>Array:push got replaced!<br>\[42\]
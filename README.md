# Nugget Script (Python)

*Yet another programming language!*

Everything is in constant movement and subject to change, but since I'm mainly working on the interpreter now, the syntax should not change all so much.

# Examples

```js
// Basic hello world
print("Hello, world!");
```
> Hello, world!

```js
// Variables are declared with `let`
let x = 1;
```

```js
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
    // same as `return "Hello, world";`
    "Hello, world!";
}

print(hello());
```
> Hello, world!

```js
print(
    x 
        => y (y +2) // Allows to reference a value inside an expression
        => (it *4)  // The name defaults to `it`
);
```
> 12

```js
// 
print(
    x
        => &y (y +1) // It currently has no practical use case, but adding an `&`
        => &(it *2)  // in front allows to run the expression while returning the base value
);                   // It could be useful for initialization, or fluent patterns where they're not supported
```
> 12

```js
let a = and();

// Creates a logic gate and connects it to the previous one
let b = and() => &{
    :connect(x);
};
```
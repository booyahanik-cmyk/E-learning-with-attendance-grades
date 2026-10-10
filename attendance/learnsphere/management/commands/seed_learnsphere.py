"""Seed LearnSphere with comprehensive academic courses, lectures, and curricula."""
from django.core.management.base import BaseCommand
from attendance.models import User
from learnsphere.models import LSCourse, LSLesson, LSEnrollment, LSProgress, LSVoucher


SEED_COURSES = [
    {
        'title': 'Python for Software Engineering & Systems',
        'category': 'Programming',
        'description': 'Master professional Python programming: idiomatic clean code, memory architecture, decorators, generators, object-oriented design patterns, and unit testing.',
        'lessons': [
            (
                'Python Architecture, Virtual Environments & The Zen of Python',
                """Welcome to Advanced Python Engineering!

Python is an interpreted, high-level, dynamically typed language known for its clear syntax and expressiveness. Beneath the surface, CPython compiles source code (.py) into bytecode (.pyc), which is subsequently executed on the Python Virtual Machine (PVM).

Key Architecture Principles:
1. CPython Bytecode & Execution Loop: Your code translates into stack-based virtual machine opcodes.
2. GIL (Global Interpreter Lock): CPython employs a mutex preventing multiple native threads from executing bytecode at once, preserving memory integrity.
3. Virtual Environments: Using `venv` isolates third-party package dependencies per project, preventing system-level package conflicts.

Recommended Setup:
```bash
python -m venv .venv
source .venv/bin/activate  # On Linux/macOS
.venv\\Scripts\\activate     # On Windows
pip install --upgrade pip
```

Takeaway: Always write idiomatic Python ("Pythonic" code) adhering to PEP 8 standards. Strive for readability, explicit behavior over implicit magic, and consistent error handling."""
            ),
            (
                'Data Structures, Memory Model & Comprehensions',
                """Deep dive into Python's built-in data structures and memory reference semantics.

Everything in Python is an object. Variables are references (names bound to memory addresses) rather than typed storage boxes.

Mutable vs Immutable Types:
- Immutable: `int`, `float`, `str`, `tuple`, `frozenset`. Any modification returns a new object in memory.
- Mutable: `list`, `dict`, `set`. Modifications mutate the object in-place without altering its memory reference ID (`id(obj)`).

List, Dict & Set Comprehensions:
Comprehensions provide a concise, idiomatic syntax for transforming iterables with lower bytecode overhead than explicit for-loops.

Example:
```python
# List comprehension with filtering
scores = [78, 92, 85, 64, 99, 45, 88]
honor_roll = [score for score in scores if score >= 85]

# Dictionary comprehension
grade_map = {f"STU_{i+1:03d}": score for i, score in enumerate(honor_roll)}
print(grade_map)
```

Takeaway: Leverage comprehensions for clear data transformations, but avoid overly nested one-liners that harm readability."""
            ),
            (
                'Iterators, Generators & Memory-Efficient Streaming',
                """Learn how Python handles massive datasets without exhausting system RAM through the Iterator Protocol.

The Iterator Protocol:
An iterable is an object that implements `__iter__()`. An iterator is an object that implements both `__iter__()` and `__next__()`. When all elements are exhausted, `StopIteration` is raised.

Generators:
Generators are functions that preserve state between executions using the `yield` keyword. Unlike lists that allocate memory for all elements immediately, generators produce values lazily on-demand (O(1) memory overhead).

Example Generator:
```python
def fibonacci_stream(limit):
    a, b = 0, 1
    count = 0
    while count < limit:
        yield a
        a, b = b, a + b
        count += 1

# Consuming stream lazily
for val in fibonacci_stream(10):
    print(val, end=" ")
```

Takeaway: Use generator expressions `(x for x in iterable)` when processing large log files, database query sets, or streaming API responses."""
            ),
            (
                'Object-Oriented Design, Dunder Methods & Encapsulation',
                """Architecting scalable software components with Python's object-oriented system.

In Python, classes are first-class citizens. "Dunder" (double underscore) special methods allow classes to hook into Python's core language operations such as arithmetic, string formatting, iteration, and equality comparisons.

Crucial Special Methods:
- `__init__(self, ...)`: Instance initializer.
- `__repr__(self)`: Unambiguous technical representation (useful in debugging).
- `__str__(self)`: Human-readable display string.
- `__eq__(self, other)`: Equality operator (`==`) behavior.

Example:
```python
class StudentCourseRecord:
    def __init__(self, course_code: str, credits: int, grade_point: float):
        self.course_code = course_code
        self.credits = credits
        self.grade_point = grade_point

    @property
    def quality_points(self) -> float:
        return self.credits * self.grade_point

    def __repr__(self) -> str:
        return f"StudentCourseRecord(code={self.course_code!r}, credits={self.credits})"
```

Takeaway: Favor `@property` decorators for getter/setter encapsulation rather than writing boilerplate Java-style getters."""
            ),
            (
                'Functional Patterns: Decorators, Closures & First-Class Callbacks',
                """Harnessing the power of functions as first-class citizens and metaprogramming via decorators.

What is a Closure?
A closure is an inner function that retains access to variables in its enclosing lexical scope even after the outer function has completed execution.

What is a Decorator?
A decorator is a callable that takes another function as an argument and extends its behavior without modifying the underlying source code.

Example Timing Decorator:
```python
import functools
import time

def execution_logger(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        duration = time.perf_counter() - start
        print(f"[{func.__name__}] executed in {duration:.6f}s")
        return result
    return wrapper

@execution_logger
def compute_factorial(n):
    return 1 if n <= 1 else n * compute_factorial(n - 1)
```

Takeaway: Always use `@functools.wraps` when crafting custom decorators to preserve the wrapped function's `__name__` and docstring."""
            ),
            (
                'Robust Error Handling, Context Managers & Automated Testing',
                """Writing production-grade resilient code with custom exception hierarchies, context managers, and pytest.

Context Managers & The `with` Statement:
Context managers ensure deterministic resource acquisition and release (such as file handles, database connections, and thread locks) using `__enter__` and `__exit__`.

Example Context Manager:
```python
class ManagedTransaction:
    def __enter__(self):
        print("Begin database transaction")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            print(f"Rolling back transaction due to {exc_val}")
            return False  # Propagate exception
        print("Committing transaction successfully")
        return True
```

Testing Strategy:
- Unit Tests: Verify isolated function logic.
- Mocking: Isolate third-party API dependencies.
- Coverage: Ensure critical paths and edge cases are exercised.

Takeaway: Never catch bare `except:`; always catch specific exceptions and log the diagnostic stack trace."""
            ),
        ],
    },
    {
        'title': 'Modern Full-Stack Web Development & APIs',
        'category': 'Web Systems',
        'description': 'End-to-end web engineering: HTTP/2 protocols, modern CSS grid architecture, asynchronous JavaScript, RESTful APIs, and secure Django backend integration.',
        'lessons': [
            (
                'HTTP Protocol Lifecycle, Headers & REST Principles',
                """Understand how web browsers and backend servers communicate across the Internet.

The HTTP Request-Response Cycle:
1. DNS Resolution: Domain name resolved to server IP address.
2. TCP Handshake: 3-way SYN, SYN-ACK, ACK handshake.
3. TLS Negotiation: Secure session key establishment (HTTPS).
4. Request Dispatch: Client transmits Method (GET, POST, PUT, DELETE), URI, Headers, and Body.
5. Response Reception: Server transmits HTTP Status Code (200 OK, 201 Created, 400 Bad Request, 404 Not Found, 500 Internal Error) with content payload.

REST Constraints:
- Statelessness: Every request must carry all authentication and state credentials.
- Uniform Interface: Standard resource endpoints (e.g., `/api/students/`, `/api/grades/`).
- Idempotency: Repeating a GET, PUT, or DELETE request produces identical server state.

Takeaway: Choose appropriate HTTP methods and status codes to provide intuitive, predictable API contracts."""
            ),
            (
                'Semantic HTML5, CSS Grid & Academic Typography Systems',
                """Constructing robust, accessible document structures and responsive grid layouts.

Semantic Markup:
Replacing generic `<div>` soup with `<header>`, `<nav>`, `<main>`, `<section>`, `<article>`, `<aside>`, and `<footer>` enhances search engine optimization (SEO) and screen reader accessibility (ARIA compliance).

CSS Grid System:
CSS Grid enables true two-dimensional layout orchestration:
```css
.academic-layout {
  display: grid;
  grid-template-columns: 280px 1fr 320px;
  gap: 24px;
}

@media (max-width: 900px) {
  .academic-layout {
    grid-template-columns: 1fr;
  }
}
```

Typography Hierarchy:
ChronosClass pairs the classic serif editorial elegance of Fraunces for display headings with the legibility of Inter for body text and IBM Plex Mono for technical tabular data.

Takeaway: Build layouts mobile-first with CSS Grid and CSS Custom Properties for maintainable design systems."""
            ),
            (
                'Modern JavaScript (ES6+), The Event Loop & Async/Await',
                """Mastering asynchronous programming in the browser and interactive UI behavior.

The JavaScript Runtime & Event Loop:
JavaScript is single-threaded. Non-blocking I/O is achieved through the Call Stack, Web APIs, Microtask Queue (Promises), and Macrotask Queue (setTimeout, DOM events).

Promises and Async/Await:
```javascript
async function fetchStudentRoster(courseId) {
  try {
    const response = await fetch(`/api/courses/${courseId}/students/`);
    if (!response.ok) {
      throw new Error(`HTTP Error ${response.status}`);
    }
    const data = await response.json();
    renderRoster(data.students);
  } catch (err) {
    console.error("Failed to load roster:", err);
    showToast("Network error loading student roster.", "error");
  }
}
```

Takeaway: Always wrap `await` calls in `try...catch` blocks to gracefully handle network failures and API errors."""
            ),
            (
                'Django MVT Architecture & The Request-Response Cycle',
                """Understanding Django's Model-View-Template pattern and server-side request pipelines.

How Django Handles a Request:
1. `urls.py`: URL patterns resolve the path and extract route parameters.
2. Middleware: Global hooks process authentication, session cookies, and CSRF protection.
3. `views.py`: Business logic queries the ORM models and compiles context dictionaries.
4. `models.py`: Database tables abstracted into Python classes with validation.
5. Templates: Django Template Engine renders dynamic HTML sent back to the client.

Template Inheritance:
ChronosClass uses a base master layout (`attendance/base.html`) that standardizes navigation, session headers, and responsive footers across Attendance, Grades, and LearnSphere.

Takeaway: Keep views thin and models thick; encapsulate business logic inside model methods whenever practical."""
            ),
            (
                'Web Security Fundamentals: CSRF, XSS & Session Hardening',
                """Protecting educational web portals against common web application vulnerabilities (OWASP Top 10).

1. Cross-Site Request Forgery (CSRF):
Attackers forge unauthorized requests from authenticated users. Django mitigates this by embedding `{% csrf_token %}` hidden tokens validated on all state-changing POST/PUT requests.

2. Cross-Site Scripting (XSS):
Malicious scripts injected into inputs rendered to other users. Django auto-escapes template variables by default unless explicitly tagged with `|safe`.

3. SQL Injection:
Never concatenate raw strings into SQL queries. Always utilize Django ORM parameterized queries (`Course.objects.filter(code=param)`).

Takeaway: Security must be baked in by default; enforce HTTPS, secure cookies, and strict input validation."""
            ),
        ],
    },
    {
        'title': 'Relational Database Architecture & SQL Mastery',
        'category': 'Databases',
        'description': 'From relational algebra to high-throughput schema design: normalization, subqueries, indexing, execution plans, and ACID transaction isolation.',
        'lessons': [
            (
                'Relational Theory, Tables, Primary Keys & Foreign Keys',
                """The mathematical foundations of relational database management systems (RDBMS).

Entities and Attributes:
Data is organized into Relations (Tables), Tuples (Rows), and Attributes (Columns).

Key Constraints:
- Primary Key (PK): Uniquely identifies each row; cannot be NULL.
- Foreign Key (FK): Enforces referential integrity by linking child records to valid parent rows.
- Unique Constraints: Prevents duplicate column values (e.g., student roll numbers or email addresses).

Example Schema:
```sql
CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    roll_number VARCHAR(20) NOT NULL UNIQUE,
    full_name VARCHAR(120) NOT NULL,
    department_id INT REFERENCES departments(id) ON DELETE RESTRICT
);
```

Takeaway: Always enforce constraints at the database level rather than relying solely on application validation."""
            ),
            (
                'Advanced SQL: Complex JOINs, Subqueries & CTEs',
                """Formulating multi-table queries for reporting and analytics.

Join Types:
- `INNER JOIN`: Returns rows with matches in both tables.
- `LEFT OUTER JOIN`: Returns all left table rows and matched right rows (NULL if no match).
- `FULL OUTER JOIN`: Returns all rows when there is a match in either table.

Common Table Expressions (CTEs):
CTEs (`WITH` clause) clarify complex nested subqueries into readable pipeline stages.

```sql
WITH AttendanceSummary AS (
    SELECT 
        student_id,
        COUNT(*) AS total_classes,
        SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) AS attended_classes
    FROM attendance_records
    GROUP BY student_id
)
SELECT 
    s.roll_number,
    s.full_name,
    a.attended_classes,
    ROUND((a.attended_classes::FLOAT / a.total_classes) * 100, 1) AS attendance_pct
FROM AttendanceSummary a
JOIN students s ON s.id = a.student_id
WHERE (a.attended_classes::FLOAT / a.total_classes) < 0.75;
```

Takeaway: Use CTEs to break down intricate analytical queries into modular, testable steps."""
            ),
            (
                'Database Normalization: From 1NF to BCNF',
                """Eliminating data redundancy and update anomalies through systematic normalization.

Normal Forms:
1. First Normal Form (1NF): Attribute values must be atomic; no repeating groups or arrays.
2. Second Normal Form (2NF): Must be in 1NF and all non-key attributes fully functionally dependent on the entire primary key (eliminates partial key dependencies).
3. Third Normal Form (3NF): Must be in 2NF and eliminate transitive dependencies (non-key attribute depending on another non-key attribute).
4. Boyce-Codd Normal Form (BCNF): A stricter version of 3NF where for every dependency X -> Y, X must be a superkey.

Takeaway: Normalize schemas to 3NF for OLTP transactional consistency, and denormalize selectively for read-heavy reporting."""
            ),
            (
                'Indexing Internals: B-Trees, Hash Indexes & EXPLAIN Plans',
                """Understanding how database storage engines locate rows and optimize query performance.

How B-Tree Indexes Work:
Without an index, the database engine must execute a sequential table scan (O(N) operations). A B-Tree index maintains a balanced multi-way tree sorted on key columns, reducing query searches to O(log N) page reads.

Query Execution Plans:
Use `EXPLAIN ANALYZE` to inspect how the planner intends to resolve a query:
```sql
EXPLAIN ANALYZE
SELECT * FROM grade_records 
WHERE student_id = 42 AND semester = 5;
```

Index Strategies:
- Single-column vs Composite Indexes: In composite index `(student_id, semester)`, order matters (the leftmost prefix rule).
- Overhead: Indexes accelerate SELECT reads but add maintenance cost during INSERT, UPDATE, and DELETE operations.

Takeaway: Index foreign keys and frequently filtered columns, but avoid excessive indexing that degrades write speed."""
            ),
            (
                'ACID Transactions & Concurrency Isolation Levels',
                """Maintaining database integrity under heavy multi-user concurrent traffic.

ACID Guarantees:
- Atomicity: All operations in a transaction succeed, or the entire transaction rolls back.
- Consistency: The database transitions from one valid state to another, obeying all constraints.
- Isolation: Concurrent transactions do not interfere with one another's intermediate states.
- Durability: Committed changes survive system crashes or power failures.

ANSI Isolation Levels:
1. Read Uncommitted: Susceptible to Dirty Reads.
2. Read Committed: Default in PostgreSQL; avoids Dirty Reads, permits Non-Repeatable Reads.
3. Repeatable Read: Guarantees consistent snapshot; avoids Non-Repeatable Reads.
4. Serializable: Strictest isolation; prevents Phantom Reads via serialization locks.

Takeaway: Use atomic database transactions (`transaction.atomic()` in Django) around multi-table write operations."""
            ),
        ],
    },
    {
        'title': 'Data Structures, Algorithms & Problem Solving',
        'category': 'Algorithms',
        'description': 'Master the core foundational algorithms: Big-O analysis, linked lists, trees, graphs, dynamic programming, and greedy optimization.',
        'lessons': [
            (
                'Asymptotic Analysis: Big-O, Big-Omega & Space-Time Tradeoffs',
                r"""Quantifying the efficiency and scalability of computational algorithms.

Formal Definitions:
- Big-O ($O(g(n))$): Upper bound on growth rate (worst-case scenario).
- Big-Omega ($\Omega(g(n))$): Lower bound on growth rate (best-case scenario).
- Big-Theta ($\Theta(g(n))$): Tight bound (both upper and lower).

Common Complexity Classes:
- $O(1)$: Constant time (hash table lookup).
- $O(\log n)$: Logarithmic time (binary search).
- $O(n)$: Linear time (array iteration).
- $O(n \log n)$: Linearithmic time (mergesort, quicksort average).
- $O(n^2)$: Quadratic time (nested loops, bubble sort).
- $O(2^n)$: Exponential time (recursive Fibonacci).

Takeaway: Optimize for space and time tradeoffs; often caching intermediate results reduces time complexity at the cost of additional memory."""
            ),
            (
                'Linear Data Structures: Stacks, Queues & Linked Lists',
                """Building and analyzing fundamental contiguous and pointer-based data structures.

Singly vs Doubly Linked Lists:
- Arrays offer $O(1)$ random access by index, but $O(n)$ insertion/deletion at arbitrary positions.
- Linked lists provide $O(1)$ node insertion/deletion once the position pointer is known, but $O(n)$ search time.

Stack (LIFO - Last In, First Out):
- Applications: Function call stacks, expression evaluation, syntax validation (balanced parentheses).

Queue (FIFO - First In, First Out):
- Applications: Task scheduling, print buffers, breadth-first search queues.

Takeaway: Use Python's `collections.deque` for double-ended queues with $O(1)$ appends and pops from both ends."""
            ),
            (
                'Binary Search Trees, AVL Balancing & Tree Traversals',
                r"""Hierarchical data representation and balanced search tree mechanics.

Binary Search Tree (BST) Invariant:
For any given node $N$, all nodes in its left subtree have keys $< N$, and all nodes in its right subtree have keys $> N$.

Tree Traversals:
1. In-order (Left, Root, Right): Yields elements in sorted ascending order.
2. Pre-order (Root, Left, Right): Ideal for copying or serializing trees.
3. Post-order (Left, Right, Root): Ideal for bottom-up cleanup (e.g., directory size calculations).

Self-Balancing Trees (AVL & Red-Black Trees):
Prevent degenerate $O(n)$ linked list degradation by rotating subtrees upon insertion/deletion to guarantee $O(\log n)$ height.

Takeaway: Balanced trees are the backbone of database indexes and associative map implementations."""
            ),
            (
                'Graph Algorithms: BFS, DFS & Shortest Path (Dijkstra)',
                r"""Modeling complex networks of interconnected entities using graph theory.

Graph Representations:
- Adjacency Matrix: $O(V^2)$ memory; ideal for dense graphs.
- Adjacency List: $O(V + E)$ memory; ideal for sparse real-world networks.

Traversals:
- Breadth-First Search (BFS): Uses a queue; discovers shortest paths in unweighted graphs.
- Depth-First Search (DFS): Uses a stack or recursion; ideal for topological sorting and cycle detection.

Dijkstra's Algorithm:
Finds the shortest path from a single source vertex to all other vertices in a weighted graph with non-negative edge weights using a min-priority heap ($O((V + E) \log V)$).

Takeaway: Choose graph representation based on graph density to optimize memory consumption."""
            ),
            (
                'Dynamic Programming & The Memoization Paradigm',
                """Solving complex optimization problems by breaking them into overlapping subproblems.

Two Core Approaches:
1. Top-Down (Memoization): Recursive approach augmented with a cache storing evaluated subproblem outputs.
2. Bottom-Up (Tabulation): Iterative approach filling an array/table starting from base cases upwards.

Classic Problems:
- 0/1 Knapsack Problem
- Longest Common Subsequence (LCS)
- Coin Change & Edit Distance

Takeaway: If a problem exhibits Optimal Substructure and Overlapping Subproblems, apply Dynamic Programming to reduce exponential runtime to polynomial time."""
            ),
        ],
    },
    {
        'title': 'Applied Artificial Intelligence & Machine Learning',
        'category': 'AI & Data',
        'description': 'From statistical learning to deep neural networks: linear regression, classification algorithms, loss functions, backpropagation, and model validation.',
        'lessons': [
            (
                'The Machine Learning Landscape & Data Preprocessing',
                """Introduction to empirical learning paradigms, feature engineering, and data pipelines.

Paradigms of Machine Learning:
1. Supervised Learning: Learning a mapping from labeled input-output pairs $(X, y)$ (regression and classification).
2. Unsupervised Learning: Discovering latent structures within unlabeled inputs (clustering, dimensionality reduction).
3. Reinforcement Learning: Agents learning optimal policy actions via environmental rewards.

Data Preprocessing Pipeline:
- Imputation: Handling missing values via mean, median, or KNN imputers.
- Feature Scaling: StandardScaler (Z-score normalization) vs MinMaxScaler.
- Encoding: One-Hot Encoding for nominal categories vs Ordinal Encoding for ranked variables.

Takeaway: Garbage in, garbage out; 80% of machine learning success lies in data cleaning and feature engineering."""
            ),
            (
                'Linear & Logistic Regression with Gradient Descent',
                r"""The mathematical bedrock of continuous and probabilistic predictive modeling.

Linear Regression:
Models the relationship: $y = \mathbf{w}^T \mathbf{x} + b$.
Minimizes the Mean Squared Error (MSE) loss function:
$$J(\mathbf{w}, b) = \\frac{1}{2m} \\sum_{i=1}^m (\\hat{y}^{(i)} - y^{(i)})^2$$

Gradient Descent Optimization:
Iteratively updates weights in the opposite direction of the gradient:
$$\\mathbf{w} \\leftarrow \\mathbf{w} - \\alpha \\nabla_{\\mathbf{w}} J$$

Logistic Regression:
Passes linear logits through the Sigmoid activation function to constrain outputs to probability intervals $[0, 1]$:
$$\\sigma(z) = \\frac{1}{1 + e^{-z}}$$

Takeaway: Grasping gradient descent and cost functions is essential for understanding deep learning architectures."""
            ),
            (
                'Decision Trees, Random Forests & Ensemble Methods',
                """Non-linear modeling, bagging, and boosting ensemble architectures.

Decision Trees:
Recursively split feature space based on impurity metrics:
- Gini Impurity: Measures probability of incorrect classification.
- Information Gain (Shannon Entropy): Measures reduction in disorder.

Ensemble Techniques:
- Bagging (Random Forests): Trains multiple independent trees on bootstrapped data subsets and averages their votes to reduce variance.
- Boosting (XGBoost, LightGBM): Trains sequential trees where each subsequent learner focuses on correcting errors made by previous iterations.

Takeaway: Gradient boosted decision trees remain the gold standard for structured tabular datasets."""
            ),
            (
                'Neural Networks: Perceptrons, Activations & Backpropagation',
                """Deep learning fundamentals: building multi-layer perceptrons and computing gradients.

Architecture of a Multi-Layer Perceptron (MLP):
- Input Layer $\\rightarrow$ Hidden Layers with non-linear activations (ReLU, GELU, Sigmoid) $\\rightarrow$ Output Layer (Softmax for multi-class classification).

Backpropagation:
Applies the calculus Chain Rule backwards from the loss function through every hidden layer weight matrix, calculating partial derivatives $\\frac{\\partial L}{\\partial W}$ to update weights via optimizers like Adam or SGD.

Takeaway: Non-linear activation functions enable neural networks to approximate arbitrary continuous functions (Universal Approximation Theorem)."""
            ),
            (
                'Model Evaluation, Cross-Validation & Overfitting Mitigations',
                """Evaluating models rigorously without succumbing to data leakage or catastrophic overfitting.

Evaluation Metrics:
- Accuracy: Misleading when dealing with imbalanced datasets.
- Precision: True Positives / (True Positives + False Positives) (critical in spam filtering).
- Recall: True Positives / (True Positives + False Negatives) (critical in disease diagnosis).
- F1-Score: Harmonic mean of Precision and Recall.
- ROC-AUC: Measures classification discriminative ability across all decision thresholds.

Overfitting Prevention:
- Train / Validation / Test Splits (typically 70/15/15)
- K-Fold Cross-Validation
- L1 (Lasso) and L2 (Ridge) Weight Regularization
- Early Stopping and Dropout layers

Takeaway: Never evaluate your final model on data seen during training or hyperparameter tuning."""
            ),
        ],
    },
    {
        'title': 'Cloud Infrastructure, Linux & DevOps Essentials',
        'category': 'Cloud & DevOps',
        'description': 'Modern deployment and operations: Linux administration, Docker containers, multi-stage builds, CI/CD automated pipelines, and cloud networking.',
        'lessons': [
            (
                'Linux Systems Administration & Shell Automation',
                """Mastering the operating system powering 96% of top web servers and cloud workloads.

Essential Linux Concepts:
- Filesystem Hierarchy: `/etc` (config), `/var` (logs), `/home` (users), `/bin` (executables).
- Permissions & Ownership: `chmod` (numeric octal permissions 755/644) and `chown`.
- Process Management: `ps aux`, `top`, `htop`, `kill -9`, and `systemctl` for daemon management.

Shell Automation Script:
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "Deploying application update..."
git pull origin main
python manage.py migrate --noinput
python manage.py collectstatic --noinput
systemctl restart gunicorn
echo "Deployment completed successfully!"
```

Takeaway: Writing safe bash scripts with `set -euo pipefail` prevents silent failures from propagating in production."""
            ),
            (
                'Containerization with Docker & Multi-Stage Builds',
                """Packaging applications into lightweight, reproducible, isolated containers.

Virtual Machines vs Containers:
- VMs emulate complete hardware with guest operating systems.
- Containers share the host Linux kernel, isolating user space via namespaces and cgroups, yielding sub-second boot times and minimal overhead.

Production Dockerfile:
```dockerfile
# Stage 1: Build dependencies
FROM python:3.13-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Minimal runtime image
FROM python:3.13-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . /app
USER 1001
CMD ["gunicorn", "maind.wsgi:application", "--bind", "0.0.0.0:8000"]
```

Takeaway: Always run containers as non-root users and leverage multi-stage builds to minimize image attack surfaces."""
            ),
            (
                'Continuous Integration & Continuous Deployment (CI/CD)',
                """Automating test suites, linting checks, security audits, and deployment pipelines.

CI/CD Pipeline Stages:
1. Lint & Format: Flake8, Black, Ruff, ESLint.
2. Static Analysis: Bandit for Python security flaws, Trivy for container vulnerabilities.
3. Automated Tests: Unit tests, integration tests with PostgreSQL and Redis testcontainers.
4. Build Artifacts: Docker image tagged with git commit SHA and pushed to registry.
5. Deploy: Blue-green or canary release onto target production server.

Takeaway: Treat your delivery pipeline as code; every pull request should pass automated gates before human merge."""
            ),
            (
                'Cloud Networking: VPCs, Subnets, DNS & Load Balancing',
                """Architecting fault-tolerant, secure network topology in cloud environments.

Network Architecture Building Blocks:
- Virtual Private Cloud (VPC): Isolated virtual software-defined network.
- Public Subnets: Host internet-facing Application Load Balancers and reverse proxies.
- Private Subnets: Host application servers and database clusters with no direct public IPs.
- NAT Gateway: Enables private subnet resources to fetch external packages without inbound internet exposure.
- Reverse Proxy & SSL Termination: Nginx decrypts TLS traffic before routing requests to backend instances.

Takeaway: Never place database instances in public subnets; enforce least-privilege network access rules."""
            ),
            (
                'Site Reliability Engineering & Production Observability',
                """Monitoring uptime, latency, error rates, and system saturation in production environments.

The Three Pillars of Observability:
1. Metrics: Time-series telemetry (CPU, memory, request latency, throughput, error rates).
2. Logs: Structured JSON application event logs indexed in centralized aggregators.
3. Distributed Traces: Tracing request spans across microservices to isolate latency bottlenecks.

The Four Golden Signals:
- Latency: Time required to service a request.
- Traffic: Demand placed on your system (requests per second).
- Errors: Rate of requests failing explicitly or implicitly.
- Saturation: How full your service is (memory, disk, thread pool exhaustion).

Takeaway: Set alert thresholds on symptoms impacting user experience rather than low-level transient spikes."""
            ),
        ],
    },
]


class Command(BaseCommand):
    help = 'Seed the LearnSphere database with starter courses and lessons.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Wipe existing courses and re-seed from scratch.',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)

        if LSCourse.objects.exists() and not force:
            self.stdout.write(self.style.WARNING(
                'LearnSphere already has courses. Use --force to wipe and re-seed.'
            ))
            return

        # Pick instructor
        instructor = (
            User.objects.filter(role=User.Role.FACULTY).first()
            or User.objects.filter(role=User.Role.ADMIN).first()
            or User.objects.first()
        )
        if not instructor:
            self.stdout.write(self.style.ERROR('No users found in database.'))
            return

        if force:
            self.stdout.write('Clearing existing LearnSphere courses, progress, and vouchers...')
            LSVoucher.objects.all().delete()
            LSProgress.objects.all().delete()
            LSEnrollment.objects.all().delete()
            LSLesson.objects.all().delete()
            LSCourse.objects.all().delete()

        created_courses = 0
        total_lessons = 0

        for seed in SEED_COURSES:
            course = LSCourse.objects.create(
                title=seed['title'],
                category=seed['category'],
                description=seed['description'],
                icon='',
                instructor=instructor,
            )
            created_courses += 1

            for pos, (title, content) in enumerate(seed['lessons'], 1):
                LSLesson.objects.create(
                    course=course,
                    title=title,
                    content=content,
                    position=pos,
                )
                total_lessons += 1

        self.stdout.write(self.style.SUCCESS(
            f'Successfully seeded {created_courses} courses with {total_lessons} rich lectures into LearnSphere!'
        ))

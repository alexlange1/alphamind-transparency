# Contributing to Alphamind

Thank you for your interest in contributing to Alphamind! This document provides guidelines and information for contributors.

## 🚀 Quick Start

1. **Fork** the repository
2. **Clone** your fork: `git clone https://github.com/YOUR_USERNAME/alphamind.git`
3. **Install** dependencies: `make install`
4. **Create** a feature branch: `git checkout -b feature/amazing-feature`
5. **Make** your changes
6. **Test** your changes: `make test`
7. **Commit** your changes: `git commit -m 'Add amazing feature'`
8. **Push** to your branch: `git push origin feature/amazing-feature`
9. **Open** a Pull Request

## 📋 Development Setup

### Prerequisites

- **Python** 3.9+
- **Node.js** 18+
- **Foundry** (for smart contracts)
- **Git**

### Installation

```bash
# Clone the repository
git clone https://github.com/alphamind/alphamind.git
cd alphamind

# Install all dependencies
make install

# Setup environment
make setup-env
```

### Development Environment

```bash
# Start development environment
make dev

# Run tests
make test

# Format code
make format

# Lint code
make lint
```

## 🏗️ Project Structure

```
alphamind/
├── contracts/          # Smart contracts (Solidity)
│   ├── src/           # Contract source files
│   ├── test/          # Contract tests
│   └── script/        # Deployment scripts
├── subnet/            # Bittensor subnet implementation
│   ├── miner/         # Miner code
│   ├── validator/     # Validator code
│   ├── api/          # REST API
│   ├── common/       # Shared utilities
│   └── tests/        # Subnet tests
├── frontend/         # Web interface
├── docs/            # Documentation
├── tests/           # Integration tests
└── scripts/         # Deployment and utility scripts
```

## 🧪 Testing

### Running Tests

```bash
# Run all tests
make test

# Run Python tests only
make test-py

# Run smart contract tests only
make test-contracts

# Run integration tests
make test-integration

# Run with coverage
pytest tests/ --cov=subnet --cov-report=html
```

### Writing Tests

- **Unit Tests**: Test individual functions and classes
- **Integration Tests**: Test component interactions
- **Contract Tests**: Test smart contract functionality
- **End-to-End Tests**: Test complete workflows

### Test Guidelines

- Write tests for all new functionality
- Maintain >90% code coverage
- Use descriptive test names
- Mock external dependencies
- Test both success and failure cases

## 📝 Code Style

### Python

We use:
- **Black** for code formatting
- **isort** for import sorting
- **flake8** for linting
- **mypy** for type checking

```bash
# Format Python code
black subnet/ tests/
isort subnet/ tests/

# Lint Python code
flake8 subnet/ tests/
mypy subnet/
```

### JavaScript/TypeScript

We use:
- **Prettier** for code formatting
- **ESLint** for linting
- **TypeScript** for type safety

```bash
# Format JavaScript code
cd frontend && npm run format

# Lint JavaScript code
cd frontend && npm run lint
```

### Solidity

We use:
- **Forge** for formatting and testing
- **Slither** for static analysis

```bash
# Format Solidity code
cd contracts && forge fmt

# Analyze contracts
cd contracts && slither .
```

## 🔧 Development Workflow

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring
- `test/description` - Test additions

### Commit Messages

Use conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance

### Pull Request Process

1. **Title**: Clear, descriptive title
2. **Description**: Detailed description of changes
3. **Tests**: All tests pass
4. **Documentation**: Update docs if needed
5. **Review**: Address reviewer feedback

## 🐛 Bug Reports

### Before Submitting

1. Check existing issues
2. Search documentation
3. Try to reproduce the issue
4. Check if it's a known issue

### Bug Report Template

```markdown
**Description**
Clear description of the bug

**Steps to Reproduce**
1. Step 1
2. Step 2
3. Step 3

**Expected Behavior**
What you expected to happen

**Actual Behavior**
What actually happened

**Environment**
- OS: [e.g. Ubuntu 20.04]
- Python: [e.g. 3.9.7]
- Node.js: [e.g. 18.0.0]
- Foundry: [e.g. 0.2.0]

**Additional Context**
Any other context about the problem
```

## 💡 Feature Requests

### Before Submitting

1. Check existing feature requests
2. Consider if it aligns with project goals
3. Think about implementation complexity

### Feature Request Template

```markdown
**Problem Statement**
Clear description of the problem

**Proposed Solution**
Description of the proposed solution

**Alternative Solutions**
Other possible solutions considered

**Additional Context**
Any other context or screenshots
```

## 🔒 Security

### Reporting Security Issues

**DO NOT** create a public issue for security vulnerabilities.

Instead, email security@alphamind.xyz with:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Security Guidelines

- Never commit secrets or private keys
- Use environment variables for sensitive data
- Validate all inputs
- Follow secure coding practices
- Keep dependencies updated

## 📚 Documentation

### Documentation Guidelines

- Write clear, concise documentation
- Include code examples
- Keep documentation up to date
- Use proper markdown formatting
- Add diagrams when helpful

### Documentation Structure

- **README.md**: Project overview and quick start
- **docs/**: Detailed documentation
- **API.md**: API reference
- **ARCHITECTURE.md**: System architecture
- **SETUP.md**: Setup guides

## 🎯 Areas for Contribution

### High Priority

- [ ] Smart contract optimizations
- [ ] Test coverage improvements
- [ ] Documentation updates
- [ ] Bug fixes
- [ ] Performance improvements

### Medium Priority

- [ ] New features
- [ ] UI/UX improvements
- [ ] Monitoring and logging
- [ ] Deployment automation

### Low Priority

- [ ] Code refactoring
- [ ] Style improvements
- [ ] Additional examples

## 🤝 Community

### Getting Help

- **Discord**: [discord.gg/alphamind](https://discord.gg/alphamind)
- **GitHub Issues**: For bugs and feature requests
- **Documentation**: [docs.alphamind.xyz](https://docs.alphamind.xyz)

### Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please read our [Code of Conduct](CODE_OF_CONDUCT.md).

## 📄 License

By contributing to Alphamind, you agree that your contributions will be licensed under the MIT License.

## 🙏 Acknowledgments

Thank you to all contributors who have helped make Alphamind better!

---

**Questions?** Feel free to reach out to the team at team@alphamind.xyz

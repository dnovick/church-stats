---
name: Schema change
about: Propose a new or changed field on the church data schema
title: "schema: "
labels: schema
---

## Field(s)

Name, type, and whether it's optional.

## Why this belongs in the schema

What question does this field answer? Is it commonly available on church
websites, or does it require another data source?

## Source of truth

Where does the data come from — scraped, manually entered, imported?

## Backwards compatibility

Does this require a `schema_version` bump, or is it purely additive
(safe under `ChurchRecord`'s `extra="allow"`)?
